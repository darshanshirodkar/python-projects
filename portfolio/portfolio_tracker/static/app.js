document.addEventListener("DOMContentLoaded", () => {
  const taxInput = document.getElementById("tax-rate");
  const tradeForm = document.getElementById("trade-form");
  const formError = document.getElementById("form-error");
  const refreshBtn = document.getElementById("btn-refresh");

  const fmtUSD = (num) =>
    num === null || num === undefined
      ? "---"
      : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(num);

  const fmtINR = (num) =>
    num === null || num === undefined
      ? "---"
      : new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(num);

  const fmtNum = (num) =>
    num === null || num === undefined
      ? "---"
      : new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(num);

  async function loadSettings() {
    try {
      const res = await fetch("/api/settings");
      const settings = await res.json();
      if (settings.global_tax_rate !== undefined) {
        taxInput.value = settings.global_tax_rate;
      }
    } catch (err) {
      console.error("Error loading settings:", err);
    }
  }

  async function saveTaxRateSetting(val) {
    try {
      await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ global_tax_rate: val }),
      });
    } catch (err) {
      console.error("Error saving tax rate setting:", err);
    }
  }

  async function loadSummary() {
    const taxRate = taxInput.value || 0;
    try {
      const res = await fetch(`/api/summary?tax_rate=${taxRate}`);
      const data = await res.json();

      if (data.usdinr_rate) {
        document.getElementById("fx-rate").textContent = data.usdinr_rate.toFixed(2);
      }

      document.getElementById("sum-cost-usd").textContent = fmtUSD(data.usd.total_cost_basis);
      document.getElementById("sum-cost-inr").textContent = fmtINR(data.inr.total_cost_basis);

      document.getElementById("sum-val-usd").textContent = fmtUSD(data.usd.value_before_tax);
      document.getElementById("sum-val-inr").textContent = fmtINR(data.inr.value_before_tax);

      const pnlUSD = data.usd.unrealized_gain;
      const pnlEl = document.getElementById("sum-pnl-usd");
      pnlEl.textContent = fmtUSD(pnlUSD);
      pnlEl.className = `kpi-val ${pnlUSD >= 0 ? "text-pos" : "text-neg"}`;
      document.getElementById("sum-pnl-inr").textContent = fmtINR(data.inr.unrealized_gain);

      document.getElementById("sum-tax-usd").textContent = fmtUSD(data.usd.tax_owed);
      document.getElementById("sum-tax-inr").textContent = fmtINR(data.inr.tax_owed);

      document.getElementById("sum-posttax-usd").textContent = fmtUSD(data.usd.value_after_tax);
      document.getElementById("sum-posttax-inr").textContent = fmtINR(data.inr.value_after_tax);
    } catch (err) {
      console.error("Error loading summary:", err);
    }
  }

  async function loadPositions() {
    try {
      const res = await fetch("/api/positions");
      const positions = await res.json();
      const tbody = document.getElementById("positions-body");
      tbody.innerHTML = "";

      if (positions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-muted">No open positions held.</td></tr>';
        return;
      }

      const totalValue = positions.reduce((sum, p) => sum + (p.market_value || 0), 0);

      positions.forEach((p) => {
        const tr = document.createElement("tr");
        const gainClass = p.unrealized_gain >= 0 ? "text-pos" : "text-neg";
        const pctStr = p.unrealized_gain_pct !== null ? `(${p.unrealized_gain_pct.toFixed(2)}%)` : "";
        const customTaxVal = p.custom_tax_rate !== null ? p.custom_tax_rate : "";

        const allocPct = totalValue > 0 && p.market_value ? ((p.market_value / totalValue) * 100).toFixed(1) + "%" : "---";

        const inrGainStr = p.unrealized_gain_inr !== undefined ? `<br><small class="text-muted">${fmtINR(p.unrealized_gain_inr)}</small>` : "";
        const inrMktStr = p.market_value_inr !== undefined ? `<br><small class="text-muted">${fmtINR(p.market_value_inr)}</small>` : "";
        const inrCostStr = p.cost_basis_inr !== undefined ? `<br><small class="text-muted">${fmtINR(p.cost_basis_inr)}</small>` : "";

        tr.innerHTML = `
          <td><strong>${p.ticker}</strong></td>
          <td><strong>${allocPct}</strong></td>
          <td>${fmtNum(p.quantity)}</td>
          <td>${fmtUSD(p.avg_cost)}</td>
          <td>${p.price_error ? '<span class="text-neg">Error</span>' : fmtUSD(p.current_price)}</td>
          <td>${fmtUSD(p.cost_basis)}${inrCostStr}</td>
          <td>${fmtUSD(p.market_value)}${inrMktStr}</td>
          <td class="${p.price_error ? '' : gainClass}">${fmtUSD(p.unrealized_gain)} ${pctStr}${inrGainStr}</td>
          <td>
            <input 
              type="number" 
              class="table-tax-input" 
              data-id="${p.id}" 
              placeholder="Default" 
              value="${customTaxVal}" 
              min="0" max="100" step="0.5"
            />
          </td>
          <td>
            <button class="btn-danger btn-del" data-id="${p.id}">CLOSE</button>
          </td>
        `;
        tbody.appendChild(tr);
      });

      document.querySelectorAll(".table-tax-input").forEach((input) => {
        input.addEventListener("change", async (e) => {
          const id = e.target.getAttribute("data-id");
          const val = e.target.value;
          await fetch(`/api/position/${id}/tax_rate`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ custom_tax_rate: val }),
          });
          loadSummary();
        });
      });

      document.querySelectorAll(".btn-del").forEach((btn) => {
        btn.addEventListener("click", async (e) => {
          if (confirm("Are you sure you want to force close/delete this position entry?")) {
            const id = e.target.getAttribute("data-id");
            await fetch(`/api/position/${id}`, { method: "DELETE" });
            refreshAll();
          }
        });
      });
    } catch (err) {
      console.error("Error loading positions:", err);
    }
  }

  async function loadTransactions() {
    try {
      const res = await fetch("/api/transactions");
      const txs = await res.json();
      const tbody = document.getElementById("transactions-body");
      tbody.innerHTML = "";

      if (txs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-muted">No transactions recorded.</td></tr>';
        return;
      }

      txs.forEach((t) => {
        const tr = document.createElement("tr");
        const actionClass = t.action === "BUY" ? "text-pos" : "text-neg";
        const dateStr = new Date(t.timestamp).toLocaleString();
        const realizedStr = t.realized_gain !== null ? fmtUSD(t.realized_gain) : "---";
        const enteredPriceStr = t.currency === "INR" ? fmtINR(t.price) : fmtUSD(t.price);

        tr.innerHTML = `
          <td>${dateStr}</td>
          <td class="${actionClass}"><strong>${t.action}</strong></td>
          <td><strong>${t.ticker}</strong></td>
          <td>${fmtNum(t.quantity)}</td>
          <td>${enteredPriceStr} (${t.currency})</td>
          <td>${fmtUSD(t.price_usd)}</td>
          <td>${realizedStr}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error("Error loading transactions:", err);
    }
  }

  function refreshAll() {
    loadSummary();
    loadPositions();
    loadTransactions();
  }

  taxInput.addEventListener("change", async () => {
    const val = taxInput.value || 0;
    await saveTaxRateSetting(val);
    loadSummary();
  });

  refreshBtn.addEventListener("click", refreshAll);

  tradeForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    formError.classList.add("hidden");

    const payload = {
      ticker: document.getElementById("tx-ticker").value,
      action: document.getElementById("tx-action").value,
      currency: document.getElementById("tx-currency").value,
      quantity: parseFloat(document.getElementById("tx-qty").value),
      price: parseFloat(document.getElementById("tx-price").value),
    };

    try {
      const res = await fetch("/api/transaction", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok) {
        formError.textContent = data.error || "An error occurred";
        formError.classList.remove("hidden");
        return;
      }

      tradeForm.reset();
      refreshAll();
    } catch (err) {
      formError.textContent = "Failed to communicate with server.";
      formError.classList.remove("hidden");
    }
  });

  (async () => {
    await loadSettings();
    refreshAll();
  })();
});