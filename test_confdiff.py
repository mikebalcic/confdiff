import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "confdiff.py"


def run(*args):
    # 显式指定 encoding：中文 Windows 的默认编码是 GBK，
    # 而子进程输出的是 UTF-8，text=True 不指定编码会解码失败。
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def test_json_diff():
    old = HERE / "_old.json"
    new = HERE / "_new.json"
    old.write_text(json.dumps({"port": 80, "db": {"host": "a", "port": 5432}}), encoding="utf-8")
    new.write_text(json.dumps({"port": 8080, "db": {"host": "b", "port": 5432}, "debug": True}),
                   encoding="utf-8")
    result = run(str(old), str(new), "--json")
    assert result.returncode == 1, result
    payload = json.loads(result.stdout)
    kinds = {c["key"]: c["kind"] for c in payload}
    assert kinds["port"] == "changed", kinds
    assert kinds["db.host"] == "changed", kinds
    assert kinds["debug"] == "added", kinds
    assert "db.port" not in kinds, kinds
    old.unlink()
    new.unlink()


def test_env_diff_and_ignore():
    old = HERE / "_old.env"
    new = HERE / "_new.env"
    old.write_text("A=1\nB=2\n", encoding="utf-8")
    new.write_text("A=1\nB=3\nDEBUG=true\n", encoding="utf-8")
    result = run(str(old), str(new), "--ignore", "^DEBUG")
    assert "DEBUG" not in result.stdout, result.stdout
    assert "B" in result.stdout
    old.unlink()
    new.unlink()


def test_whitespace_only():
    old = HERE / "_old.ini"
    new = HERE / "_new.ini"
    old.write_text("[s]\nkey=value\n", encoding="utf-8")
    new.write_text("[s]\nkey = value\n", encoding="utf-8")
    result = run(str(old), str(new), "--json")
    payload = json.loads(result.stdout)
    assert payload and payload[0]["kind"] == "whitespace", payload
    old.unlink()
    new.unlink()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all tests passed")
