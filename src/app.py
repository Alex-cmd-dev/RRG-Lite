import json
import sys
import threading
from pathlib import Path

import matplotlib
matplotlib.use("TkAgg")

import tkinter as tk
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from RRG import RRG
from fetch_spdr import fetch_all

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

SPDR_ETFS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
TIMEFRAMES = ["daily", "weekly", "monthly", "quarterly"]
CONFIG_PATH = Path(__file__).parent / "user.json"


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.title("Settings")
        self.resizable(False, False)
        self.result = None

        ttk.Label(self, text="API Host:").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.host_var = tk.StringVar(value=config.get("API_HOST", "http://localhost:8080"))
        ttk.Entry(self, textvariable=self.host_var, width=32).grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(self, text="API Key:").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        self.key_var = tk.StringVar(value=config.get("API_KEY", "dev-api-key"))
        ttk.Entry(self, textvariable=self.key_var, width=32).grid(row=1, column=1, padx=10, pady=8)

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=6)

        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _save(self):
        self.result = {
            "API_HOST": self.host_var.get().strip(),
            "API_KEY": self.key_var.get().strip(),
        }
        self.destroy()


class RRGApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RRG-Lite")
        self.geometry("1280x860")

        self._rrg_cids = []
        self._fetching = False
        self.config_data = self._load_config()

        self._build_controls()
        self._build_chart_area()
        self._build_status_bar()

        # Plot on startup with cached CSV data
        self.after(100, self._plot)

    def _load_config(self):
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_bytes())
        return {}

    def _save_config(self):
        CONFIG_PATH.write_text(json.dumps(self.config_data, indent=2) + "\n")

    def _build_controls(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=8, pady=6)

        row1 = ttk.Frame(top)
        row1.pack(fill=tk.X)

        ttk.Label(row1, text="Benchmark:").pack(side=tk.LEFT)
        self.benchmark_var = tk.StringVar(value=self.config_data.get("BENCHMARK", "SPY"))
        ttk.Entry(row1, textvariable=self.benchmark_var, width=8).pack(side=tk.LEFT, padx=(3, 12))

        ttk.Label(row1, text="Timeframe:").pack(side=tk.LEFT)
        self.tf_var = tk.StringVar(value=self.config_data.get("DEFAULT_TF", "weekly"))
        ttk.Combobox(row1, textvariable=self.tf_var, values=TIMEFRAMES, width=10, state="readonly").pack(
            side=tk.LEFT, padx=(3, 12)
        )

        ttk.Label(row1, text="Tail:").pack(side=tk.LEFT)
        self.tail_var = tk.IntVar(value=4)
        ttk.Spinbox(row1, from_=2, to=20, textvariable=self.tail_var, width=4).pack(
            side=tk.LEFT, padx=(3, 12)
        )

        ttk.Button(row1, text="Plot", command=self._plot).pack(side=tk.LEFT, padx=(0, 6))
        self._refresh_btn = ttk.Button(row1, text="Refresh Data", command=self._refresh_data)
        self._refresh_btn.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(row1, text="Settings", command=self._open_settings).pack(side=tk.LEFT)

        sym_frame = ttk.LabelFrame(top, text="Sectors")
        sym_frame.pack(fill=tk.X, pady=(6, 0))

        self.sym_vars = {}
        for etf in SPDR_ETFS:
            var = tk.BooleanVar(value=True)
            self.sym_vars[etf] = var
            ttk.Checkbutton(sym_frame, text=etf, variable=var).pack(side=tk.LEFT, padx=5, pady=3)

    def _build_chart_area(self):
        self.fig = Figure()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)

        nav = NavigationToolbar2Tk(self.canvas, self)
        nav.update()
        nav.pack(fill=tk.X)

        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=(6, 2)).pack(
            fill=tk.X, side=tk.BOTTOM
        )

    def _plot(self):
        for cid in self._rrg_cids:
            try:
                self.fig.canvas.mpl_disconnect(cid)
            except Exception:
                pass
        self._rrg_cids.clear()

        self.fig.clear()

        symbols = [etf for etf, var in self.sym_vars.items() if var.get()]
        benchmark = self.benchmark_var.get().strip()

        if not symbols:
            self.status_var.set("Select at least one sector.")
            self.canvas.draw()
            return

        if not self.config_data.get("DATA_PATH"):
            self.status_var.set("Error: DATA_PATH not set — edit Settings or check src/user.json.")
            return

        try:
            rrg = RRG(
                self.config_data,
                watchlist=symbols,
                tail_count=self.tail_var.get(),
                benchmark=benchmark,
                tf=self.tf_var.get(),
            )
            axs = self.fig.add_subplot(111)
            cids = rrg.plot(fig=self.fig, axs=axs)
            if cids:
                self._rrg_cids.extend(cids)
            self.fig.tight_layout()
        except Exception as e:
            self.status_var.set(f"Error: {e}")
            self.canvas.draw()
            return

        self.canvas.draw()
        self.status_var.set(f"Plotted {len(symbols)} sectors vs {benchmark.upper()}")

    def _refresh_data(self):
        if self._fetching:
            return

        host = self.config_data.get("API_HOST", "http://localhost:8080")
        api_key = self.config_data.get("API_KEY", "dev-api-key")
        data_path = self.config_data.get("DATA_PATH", "data")

        self._fetching = True
        self._refresh_btn.config(state="disabled")
        self.status_var.set("Fetching data...")

        def do_fetch():
            try:
                success, failed = fetch_all(
                    host=host,
                    api_key=api_key,
                    out_dir=Path(data_path),
                    progress_cb=lambda msg: self.after(0, lambda m=msg: self.status_var.set(m)),
                )

                def done():
                    self._fetching = False
                    self._refresh_btn.config(state="normal")
                    if failed:
                        self.status_var.set(
                            f"Done: {len(success)} fetched, {len(failed)} failed ({', '.join(failed)}). Click Plot to refresh."
                        )
                    else:
                        self.status_var.set(
                            f"Done: all {len(success)} symbols fetched. Click Plot to refresh chart."
                        )

                self.after(0, done)
            except Exception as e:
                def on_error(err=e):
                    self._fetching = False
                    self._refresh_btn.config(state="normal")
                    self.status_var.set(f"Fetch error: {err}")
                self.after(0, on_error)

        threading.Thread(target=do_fetch, daemon=True).start()

    def _open_settings(self):
        dlg = SettingsDialog(self, self.config_data)
        if dlg.result:
            self.config_data.update(dlg.result)
            self._save_config()
            self.status_var.set("Settings saved.")


if __name__ == "__main__":
    app = RRGApp()
    app.mainloop()
