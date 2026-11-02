"""Respaldos de la base de datos con mysqldump (en un hilo, sin bloquear la interfaz)."""
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
KEEP_LAST = 14


def run_backup(config: dict) -> Path:
    """Genera backups/farmastock_AAAAMMDD_HHMMSS.sql y conserva solo los últimos KEEP_LAST."""
    exe = shutil.which("mysqldump")
    if not exe:
        raise RuntimeError("No se encontró 'mysqldump'. Agrega la carpeta bin de MySQL al PATH.")
    BACKUP_DIR.mkdir(exist_ok=True)
    target = BACKUP_DIR / f"{config['database']}_{datetime.now():%Y%m%d_%H%M%S}.sql"
    cmd = [exe, f"--host={config['host']}", f"--port={config['port']}", f"--user={config['user']}",
           "--single-transaction", "--routines", f"--result-file={target}", config["database"]]
    env = {**os.environ, "MYSQL_PWD": config["password"]}  # evita pasar la clave en la línea de comandos
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "mysqldump falló.")
    for old in sorted(BACKUP_DIR.glob("*.sql"))[:-KEEP_LAST]:
        old.unlink(missing_ok=True)
    return target


class _Signals(QObject):
    finished = Signal(str)
    failed = Signal(str)


class _BackupTask(QRunnable):
    def __init__(self, config: dict):
        super().__init__(); self.config = config; self.signals = _Signals()

    def run(self) -> None:
        try:
            self.signals.finished.emit(str(run_backup(self.config)))
        except Exception as exc:  # se informa a la interfaz por señal
            self.signals.failed.emit(str(exc))


class BackupService(QObject):
    """Respaldo manual y automático (al iniciar y cada 6 horas) en segundo plano."""
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, db, interval_hours: int = 6):
        super().__init__(); self.db = db
        self.timer = QTimer(self); self.timer.timeout.connect(self.start)
        self.timer.start(interval_hours * 3600 * 1000)

    def start(self) -> None:
        task = _BackupTask(self.db.config)
        task.signals.finished.connect(self.finished); task.signals.failed.connect(self.failed)
        QThreadPool.globalInstance().start(task)
