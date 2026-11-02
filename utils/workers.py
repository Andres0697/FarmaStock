"""Tareas pesadas en segundo plano con QThread, comunicadas por señales y slots.

El hilo secundario NUNCA toca widgets: solo ejecuta la función recibida y emite señales
(`progress`, `succeeded`, `failed`) que la ventana recibe en el hilo de la interfaz.
"""
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QProgressDialog


class TaskWorker(QThread):
    progress = Signal(int, str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self._func = func

    def report(self, percent: int, message: str = "") -> None:
        """Informa avance (0-100). Se llama desde `func`; emite una señal, no toca la UI."""
        self.progress.emit(int(percent), message)

    @property
    def cancelled(self) -> bool:
        return self.isInterruptionRequested()

    def run(self) -> None:
        try:
            result = self._func(self)
        except Exception as exc:  # se informa a la interfaz por señal; no se pierde el error
            self.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)


def run_task(owner, title: str, func, on_success, on_error, cancelable: bool = True) -> TaskWorker:
    """Ejecuta `func(worker)` en un QThread mostrando un diálogo de progreso.

    `on_success(resultado)` y `on_error(mensaje)` se ejecutan en el hilo de la interfaz.
    """
    dialog = QProgressDialog(title, "Cancelar" if cancelable else None, 0, 0, owner)
    dialog.setWindowTitle("FarmaStock")
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setMinimumDuration(300)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)

    worker = TaskWorker(func, owner)

    def update(percent: int, message: str) -> None:
        if percent >= 0 and dialog.maximum() == 0:
            dialog.setRange(0, 100)
        dialog.setValue(max(0, min(100, percent)))
        if message:
            dialog.setLabelText(message)

    def finish() -> None:
        dialog.close()
        dialog.deleteLater()
        worker.deleteLater()

    worker.progress.connect(update)
    # Se cierra el diálogo de progreso antes de mostrar resultados o errores.
    worker.succeeded.connect(lambda result: (dialog.close(), on_success(result)))
    worker.failed.connect(lambda message: (dialog.close(), on_error(message)))
    worker.finished.connect(finish)
    if cancelable:
        dialog.canceled.connect(worker.requestInterruption)
    worker.start()
    return worker
