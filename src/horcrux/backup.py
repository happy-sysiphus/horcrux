from __future__ import annotations

import tempfile
import threading
import time
import zipfile
from datetime import date
from pathlib import Path


def make_backup_zip(data_dir: Path) -> Path:
    out = Path(tempfile.mkdtemp()) / f"vaults-{date.today().isoformat()}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted((data_dir / "vaults").rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(data_dir).as_posix())
    return out


def upload_backup(storage, zip_path: Path) -> None:
    # storage = supabase client.storage.from_("vault-backups")
    storage.upload(zip_path.name, zip_path.read_bytes(),
                   {"content-type": "application/zip", "upsert": "true"})


def start_backup_thread(deploy, interval_sec: int = 86400,
                        first_delay_sec: int = 60) -> threading.Thread:
    def loop():
        # 재배포마다 컨테이너가 재시작돼 타이머가 리셋된다 — 첫 백업은 기동 직후에 한 번
        time.sleep(first_delay_sec)
        while True:
            try:
                z = make_backup_zip(deploy.data_dir)
                upload_backup(deploy.db._c.storage.from_("vault-backups"), z)
                print(f"백업 업로드: {z.name}")
            except Exception as e:   # 백업 실패는 서비스 영향 없음 — 다음 주기 재시도
                print(f"(백업 실패 — 다음 주기 재시도: {e})")
            time.sleep(interval_sec)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
