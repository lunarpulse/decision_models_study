"""LoRA fine-tune of decider-4b on the demo corpus (supervision parity with laya-ft).

Recipe follows Mapika's published stage 2 (MODEL_CARD_4B.md): LoRA rank 64, alpha 128 on the
attention and MLP projections, lr 1e-4, 5% warmup then cosine, 2 epochs, cross-entropy on the
slot readout; merged into bf16 weights afterwards. Per-type temperatures are re-fitted by NLL
on the validation split (their known failure mode: hard labels sharpen logits) and written to
decider_config.json in the output directory.

Runs next to the live demo stack: gradient checkpointing, small token budget per micro-batch,
expandable segments. If it OOMs it dies alone; the live services keep their reserved memory.
"""
import argparse, json, math, os, random, time
import torch, torch.nn.functional as F
from decider.model import DecisionModel, collate
from decider.prompt import build
from decider.data.core import Example, Q
from peft import LoraConfig, inject_adapter_in_model
from peft.tuners.lora import Linear as LoraLinear

TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def rows_to_examples(rows):
    exs = []
    for r in rows:
        qs = []
        for qid, q in r["questions"].items():
            if q["type"] == "noul":
                opts, gold = ["no", "yes"], int(bool(r["expected"][qid]))
            elif q["type"] == "score":
                crit = q["criteria"]
                opts, gold = list(crit), int(r["expected"][qid])
            else:
                crit = q["criteria"]
                opts = list(crit.keys())
                gold = opts.index(r["expected"][qid])
            qs.append(Q(text=q["instructions"], options=opts, gold=gold))
        exs.append(Example(context=r["state"], qs=qs, task="insurance_demo"))
    return exs


def read_jsonl(p):
    return [json.loads(l) for l in open(p)]


def loss_fn(logits, golds):
    ok = golds >= 0
    return F.cross_entropy(logits[ok], golds[ok])


@torch.no_grad()
def slot_logit_batches(model, items, tok, bs):
    for c in range(0, len(items), bs):
        b = collate(items[c:c + bs], tok.pad_token_id)
        b = {k: (v.cuda() if torch.is_tensor(v) else v) for k, v in b.items()}
        yield b["golds"].cuda(), model(b).float()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--base", default="Mapika/decider-4b")
    ap.add_argument("--out", default="decider-ft-ckpt")
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--micro-bs", type=int, default=8)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--rank", type=int, default=64)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    logf = open(f"{a.out}/train.log", "a")

    def log(*s):
        msg = " ".join(str(x) for x in s)
        print(msg, flush=True)
        logf.write(msg + "\n")
        logf.flush()

    log("[args]", json.dumps(vars(a)))
    torch.manual_seed(a.seed)
    rng = random.Random(a.seed)

    train = read_jsonl(f"{a.data_dir}/train.jsonl")
    val = read_jsonl(f"{a.data_dir}/validation.jsonl")[:400]
    train_ex, val_ex = rows_to_examples(train), rows_to_examples(val)
    log(f"[data] train {len(train_ex)} items / {sum(len(e.qs) for e in train_ex)} questions; val {len(val_ex)}")

    model = DecisionModel(a.base)
    tok = model.tok
    lcfg = LoraConfig(r=a.rank, lora_alpha=2 * a.rank, lora_dropout=0.0, bias="none",
                      target_modules=TARGET_MODULES, task_type="CAUSAL_LM")
    inject_adapter_in_model(lcfg, model.lm)
    model.lm.enable_input_require_grads()
    model.cuda().train()
    n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
    log(f"[lora] rank {a.rank} trainable params {n_train/1e6:.1f}M")

    items = [build(e, tok, rng, max_options=10, max_ctx_tokens=2048, layout="state_first")
             for e in train_ex]
    ntok = sum(len(it["ids"]) for it in items)
    log(f"[data] tokenized {len(items)} items, {ntok/1e6:.1f}M tokens")

    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=a.lr, betas=(0.9, 0.95), weight_decay=0.0)

    steps_per_epoch = math.ceil(len(items) / (a.micro_bs * a.accum))
    total = int(steps_per_epoch * a.epochs)
    warmup = max(1, int(total * 0.05))
    log(f"[sched] {steps_per_epoch} optimizer steps/epoch, {total} total, warmup {warmup}")

    def lr_at(s):
        if s < warmup:
            return a.lr * s / warmup
        return a.lr * 0.5 * (1 + math.cos(math.pi * min(1.0, (s - warmup) / max(1, total - warmup))))

    order = list(range(len(items)))
    step = micro = ep = 0
    t0 = time.time()
    while step < total:
        rng.shuffle(order)
        for c in range(0, len(order), a.micro_bs):
            if step >= total:
                break
            b = collate([items[i] for i in order[c:c + a.micro_bs]], tok.pad_token_id)
            b = {k: (v.cuda() if torch.is_tensor(v) else v) for k, v in b.items()}
            logits = model(b)
            loss = loss_fn(logits, b["golds"].cuda())
            (loss / a.accum).backward()
            micro += 1
            if micro % a.accum == 0:
                for g in opt.param_groups:
                    g["lr"] = lr_at(step)
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                opt.step()
                opt.zero_grad(set_to_none=True)
                step += 1
                if step % 10 == 0 or step == total:
                    el = (time.time() - t0) / 60
                    log(f"[train] step {step}/{total} ep {ep} loss {loss.item():.4f} lr {lr_at(step):.2e} "
                        f"{el:.1f}min mem {torch.cuda.max_memory_allocated()/1e9:.1f}GB")
        ep += 1

    log("[merge] merging LoRA into bf16 weights")
    merged_n = 0
    for parent in model.lm.modules():
        for child_name, child in list(parent.named_children()):
            if isinstance(child, LoraLinear):
                child.merge()
                setattr(parent, child_name, child.get_base_layer())
                merged_n += 1
    log(f"[merge] merged {merged_n} adapters and restored base module names")
    model.eval()
    model.lm.save_pretrained(f"{a.out}/model")
    tok.save_pretrained(f"{a.out}/model")

    # ---- per-type temperature refit on validation (NLL) ----
    val_items = [build(e, tok, rng, max_options=10, max_ctx_tokens=2048, layout="state_first")
                 for e in val_ex]
    qtypes = [q["type"] for r in val for q in r["questions"].values()]
    buckets = {"choice": ([], []), "noul": ([], []), "score": ([], [])}
    for g, lg in slot_logit_batches(model, val_items, tok, 16):
        for i, gi in enumerate(g.tolist()):
            k = qtypes[i] if qtypes[i] in buckets else "choice"
            buckets[k][0].append(gi)
            buckets[k][1].append(lg[i].cpu())
    temps = {}
    for k, (gs, ls) in buckets.items():
        if not ls:
            continue
        g, l = torch.tensor(gs), torch.stack(ls)
        best, best_nll = 1.0, float("inf")
        for T in [0.05 * j for j in range(1, 81)]:
            nll = F.cross_entropy(l / T, g).item()
            if nll < best_nll:
                best, best_nll = T, nll
        temps[k] = round(best, 3)
        log(f"[calibrate] {k}: T={temps[k]} NLL={best_nll:.4f} n={len(gs)}")
    cfg = {"temperature": round(sum(temps.values()) / max(1, len(temps)), 3),
           "temperature_by_type": temps}
    json.dump(cfg, open(f"{a.out}/model/decider_config.json", "w"), indent=1)
    log("[done] saved", f"{a.out}/model", "temps", json.dumps(cfg))


if __name__ == "__main__":
    main()
