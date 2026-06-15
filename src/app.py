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


SECTOR_INFO = {
    "XLB":  ("Materials",               "Mining, chemicals, construction materials, packaging."),
    "XLC":  ("Communication Services",  "Telecom, media, internet & entertainment companies."),
    "XLE":  ("Energy",                  "Oil, gas, and consumable fuels exploration & production."),
    "XLF":  ("Financials",              "Banks, insurance, diversified financial services."),
    "XLI":  ("Industrials",             "Aerospace, defense, machinery, transportation."),
    "XLK":  ("Technology",              "Software, hardware, semiconductors, IT services."),
    "XLP":  ("Consumer Staples",        "Food, beverages, tobacco, household products."),
    "XLRE": ("Real Estate",             "REITs and real-estate management & development."),
    "XLU":  ("Utilities",               "Electric, gas, and water utilities."),
    "XLV":  ("Health Care",             "Pharma, biotech, medical devices, health services."),
    "XLY":  ("Consumer Discretionary",  "Retail, autos, hotels, restaurants, leisure."),
}

HELP_TEXT = """\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  RELATIVE ROTATION GRAPH (RRG) — QUICK GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHAT IS AN RRG?
───────────────
A Relative Rotation Graph plots multiple assets on a
two-axis chart to show their strength and momentum
relative to a common benchmark (e.g. SPY).

Each dot represents one sector ETF. Dots rotate
clockwise through four quadrants as market leadership
shifts over time.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THE TWO AXES
────────────

  X-Axis — RS Ratio (Relative Strength)
  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
  Measures how a sector is performing versus the
  benchmark on a normalized scale centered at 100.

  • > 100  →  outperforming the benchmark
  • < 100  →  underperforming the benchmark
  • Higher = stronger relative performance

  Calculation:
    1. Divide sector price by benchmark price × 100
    2. Apply a weighted moving average (WMA)
    3. Normalize: 100 + (value − mean) / std dev

  Y-Axis — RS Momentum
  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
  Measures whether RS Ratio is accelerating or
  decelerating — the rate of change of relative
  strength.

  • > 100  →  RS Ratio is improving (gaining speed)
  • < 100  →  RS Ratio is deteriorating (slowing down)
  • Higher = faster improvement vs. benchmark

  Calculation:
    Normalize the RS Ratio series using a rolling
    window: 100 + (RS − rolling mean) / rolling std

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THE FOUR QUADRANTS
──────────────────

  🟢 LEADING   (top-right)   RS > 100, Mom > 100
     Strong AND accelerating — current market leaders.
     Best candidates for long exposure.

  🔵 IMPROVING (top-left)    RS < 100, Mom > 100
     Weak but gaining momentum — potential turn-around.
     Watch for rotation into Leading.

  🟡 WEAKENING (bottom-right) RS > 100, Mom < 100
     Strong but losing momentum — leaders fading.
     Consider reducing exposure or tightening stops.

  🔴 LAGGING   (bottom-left)  RS < 100, Mom < 100
     Weak AND decelerating — current market laggards.
     Avoid or consider short exposure.

Typical clockwise rotation:
  Leading → Weakening → Lagging → Improving → Leading

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SPDR SECTOR ETFs
────────────────
"""

for _ticker, (_name, _desc) in SECTOR_INFO.items():
    HELP_TEXT += f"  {_ticker:<5}  {_name:<26}  {_desc}\n"

HELP_TEXT += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CHART CONTROLS
──────────────
  Plot button       — Redraw chart with current settings
  Refresh Data      — Download fresh price data from API
  Tails button      — Toggle tail lines for all sectors
  Names button      — Toggle ticker labels on chart
  Tail spinbox      — Number of historical periods to show

  Click a dot       — Highlight that sector's tail
  ← / → arrow keys — Step through tail dates (when highlighted)
  [A]  key          — Toggle all text labels
  [T]  key          — Toggle all tail lines
  [H]  key          — Show/hide keyboard shortcut overlay
  [Delete] key      — Clear all highlighted tails
"""


class HelpDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("RRG Help — RS Ratio, Momentum & Sectors")
        self.geometry("660x600")
        self.resizable(True, True)

        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 4))

        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text = tk.Text(
            frame,
            wrap=tk.WORD,
            font=("Courier", 10),
            yscrollcommand=scrollbar.set,
            relief=tk.FLAT,
            padx=8,
            pady=8,
        )
        text.insert(tk.END, HELP_TEXT)
        text.config(state=tk.DISABLED)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)

        ttk.Button(self, text="Close", command=self.destroy).pack(pady=(0, 8))

        self.transient(parent)
        self.grab_set()


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
        self._rrg = None
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
        ttk.Button(row1, text="Settings", command=self._open_settings).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(row1, text="Help", command=self._open_help).pack(side=tk.LEFT)

        ttk.Separator(row1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        self._tails_btn = ttk.Button(row1, text="Tails: Off", command=self._toggle_tails, state="disabled")
        self._tails_btn.pack(side=tk.LEFT, padx=(0, 4))
        self._names_btn = ttk.Button(row1, text="Names: Off", command=self._toggle_names, state="disabled")
        self._names_btn.pack(side=tk.LEFT)

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
        self._rrg = None
        self._tails_btn.config(state="disabled", text="Tails: Off")
        self._names_btn.config(state="disabled", text="Names: Off")

        self.fig.clear()

        symbols = [etf for etf, var in self.sym_vars.items() if var.get()]
        benchmark = self.benchmark_var.get().strip()

        if not symbols:
            self.status_var.set("Select at least one sector.")
            self.canvas.draw()
            return

        if not self.config_data.get("DATA_PATH"):
            self.status_var.set("Error: DATA_PATH not set — edit Settings or check src/user.json.")
            self.canvas.draw()
            return

        tf = self.tf_var.get()
        try:
            rrg = RRG(
                self.config_data,
                watchlist=symbols,
                tail_count=self.tail_var.get(),
                benchmark=benchmark,
                tf=tf,
            )
            axs = self.fig.add_subplot(111)
            cids = rrg.plot(fig=self.fig, axs=axs)
            if cids:
                self._rrg_cids.extend(cids)
            self.fig.tight_layout()
        except ValueError as e:
            msg = str(e)
            if "insufficient" in msg.lower():
                msg = f"Not enough data for {tf} view — try Refresh Data with more years."
            self.status_var.set(f"Error: {msg}")
            self.canvas.draw()
            return
        except Exception as e:
            self.status_var.set(f"Error: {e}")
            self.canvas.draw()
            return

        self._rrg = rrg
        self._tails_btn.config(state="normal")
        self._names_btn.config(state="normal")
        self.canvas.draw()

        n = rrg.plotted_count
        skipped = rrg.skipped_tickers
        if skipped:
            self.status_var.set(
                f"Plotted {n}/{len(symbols)} sectors vs {benchmark.upper()} "
                f"({len(skipped)} skipped: {', '.join(skipped)})"
            )
        else:
            self.status_var.set(f"Plotted {n} sectors vs {benchmark.upper()}")

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

    def _toggle_tails(self):
        if self._rrg is None:
            return
        self._rrg._toggle_lines(None)
        is_on = self._rrg.line_alpha_state > 0
        self._tails_btn.config(text=f"Tails: {'On' if is_on else 'Off'}")

    def _toggle_names(self):
        if self._rrg is None:
            return
        self._rrg._toggle_text(None)
        is_on = self._rrg.text_alpha_state > 0
        self._names_btn.config(text=f"Names: {'On' if is_on else 'Off'}")

    def _open_help(self):
        HelpDialog(self)

    def _open_settings(self):
        dlg = SettingsDialog(self, self.config_data)
        if dlg.result:
            self.config_data.update(dlg.result)
            self._save_config()
            self.status_var.set("Settings saved.")


if __name__ == "__main__":
    app = RRGApp()
    app.mainloop()
