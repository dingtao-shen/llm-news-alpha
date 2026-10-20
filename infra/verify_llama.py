"""核对卷上的 LLaMA 3 权重：本地 commit 与 Hugging Face main 一致，每个 safetensors 分片的大小与 SHA-256 一致。

运行：make verify-llama（读 30GB，约几分钟）
"""
import hashlib
import json
import os
import urllib.request

TOKEN = os.environ["HF_TOKEN"]
MODELS = ["Meta-Llama-3-8B", "Meta-Llama-3-8B-Instruct"]
HUB = os.path.join(os.environ.get("HF_HOME", "/workspace/hf_cache"), "hub")


def api(url):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN})
    return json.load(urllib.request.urlopen(req))


def main():
    bad = 0
    for m in MODELS:
        root = f"{HUB}/models--meta-llama--{m}"
        local = open(root + "/refs/main").read().strip()
        remote = api(f"https://huggingface.co/api/models/meta-llama/{m}/revision/main")["sha"]
        ok = local == remote
        bad += not ok
        print(f"== {m}  commit local={local[:12]} remote={remote[:12]}  {'OK' if ok else 'MISMATCH'}")
        for f in api(f"https://huggingface.co/api/models/meta-llama/{m}/tree/main"):
            if not f["path"].endswith(".safetensors"):
                continue
            p = f"{root}/snapshots/{local}/{f['path']}"
            if not os.path.exists(p):
                print(f"   {f['path']}  MISSING")
                bad += 1
                continue
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 24), b""):
                    h.update(chunk)
            want = (f.get("lfs") or {}).get("oid")
            size_ok = os.path.getsize(p) == f["size"]
            sha_ok = want is None or h.hexdigest() == want
            bad += (not size_ok) + (not sha_ok)
            print(f"   {f['path']:<36} {f['size'] / 1e9:5.2f} GB  size {'OK' if size_ok else 'BAD'}  "
                  f"sha256 {'n/a' if want is None else ('OK' if sha_ok else 'MISMATCH')}")
    print("verify-llama ok" if bad == 0 else f"verify-llama: {bad} problem(s)")


if __name__ == "__main__":
    main()
