const state = { horizon: 91, target: "net_revenue_usd" };
const colors = { base_plan: "#233f55", upside: "#1f8a68", downside: "#ba4b47" };
let dashboard;

const money = (value, compact = false) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
    notation: compact ? "compact" : "standard",
  }).format(value);

const signedMoney = (value) => `${value > 0 ? "+" : ""}${money(value)}`;
const titleCase = (value) => value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
const scenario = (id) => dashboard.scenarios.find((item) => item.scenario_id === id);
const horizonData = (id) => scenario(id).horizons[`${state.horizon}_days`];
const forecastKey = () => state.target;
const deltaKey = () => `${state.target.replace("_usd", "")}_delta_vs_base_usd`;

function updateControls() {
  document.querySelectorAll("[data-horizon]").forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.horizon) === state.horizon);
  });
  document.querySelectorAll("[data-target]").forEach((button) => {
    button.classList.toggle("active", button.dataset.target === state.target);
  });
}

function renderKpis() {
  const base = horizonData("base_plan")[forecastKey()];
  const upside = horizonData("upside")[forecastKey()];
  const downside = horizonData("downside")[forecastKey()];
  document.querySelector("#kpi-base").textContent = money(base, true);
  document.querySelector("#kpi-base-note").textContent = `${state.horizon / 7}-week ${titleCase(state.target.replace("_usd", ""))}`;
  document.querySelector("#kpi-upside").textContent = signedMoney(upside - base);
  document.querySelector("#kpi-upside-total").textContent = `${money(upside, true)} total`;
  document.querySelector("#kpi-downside").textContent = signedMoney(downside - base);
  document.querySelector("#kpi-downside-total").textContent = `${money(downside, true)} total`;
  document.querySelector("#kpi-spread").textContent = money(upside - downside, true);

  const capacity = horizonData("capacity_relief").shipped_revenue_delta_vs_base_usd;
  document.querySelector("#decision-brief").textContent =
    `The base plan forecasts ${money(horizonData("base_plan").net_revenue_usd)} in booked net revenue. ` +
    `The upside plan adds ${money(horizonData("upside").net_revenue_delta_vs_base_usd)}, while capacity relief releases ` +
    `${money(capacity)} of additional shipped revenue without changing booked demand.`;
}

function renderChart() {
  const svg = document.querySelector("#forecast-chart");
  const width = 920, height = 330, pad = { left: 68, right: 22, top: 22, bottom: 42 };
  const ids = ["base_plan", "upside", "downside"];
  const series = ids.map((id) => dashboard.daily[id][state.target].filter((row) => row.day <= state.horizon));
  const values = series.flat().map((row) => row.forecast);
  const min = Math.min(...values) * 0.96;
  const max = Math.max(...values) * 1.04;
  const x = (index) => pad.left + (index / Math.max(state.horizon - 1, 1)) * (width - pad.left - pad.right);
  const y = (value) => pad.top + ((max - value) / (max - min)) * (height - pad.top - pad.bottom);
  const parts = [];

  for (let tick = 0; tick <= 4; tick += 1) {
    const value = min + ((max - min) * tick) / 4;
    const yPos = y(value);
    parts.push(`<line class="grid-line" x1="${pad.left}" y1="${yPos}" x2="${width - pad.right}" y2="${yPos}" />`);
    parts.push(`<text class="axis-label" x="${pad.left - 10}" y="${yPos + 4}" text-anchor="end">${money(value, true)}</text>`);
  }
  [1, Math.ceil(state.horizon / 2), state.horizon].forEach((day) => {
    const row = series[0][day - 1];
    parts.push(`<text class="axis-label" x="${x(day - 1)}" y="${height - 13}" text-anchor="middle">${row.date.slice(5)}</text>`);
  });
  series.forEach((rows, index) => {
    const id = ids[index];
    const points = rows.map((row, pointIndex) => `${x(pointIndex)},${y(row.forecast)}`).join(" ");
    parts.push(`<polyline class="chart-line" stroke="${colors[id]}" points="${points}" />`);
  });
  svg.innerHTML = parts.join("");
}

function renderScenarioBars() {
  const rows = dashboard.scenarios
    .map((item) => ({ ...item, value: item.horizons[`${state.horizon}_days`][forecastKey()] }))
    .sort((a, b) => b.value - a.value);
  const min = Math.min(...rows.map((row) => row.value));
  const max = Math.max(...rows.map((row) => row.value));
  document.querySelector("#scenario-bars").innerHTML = rows.map((row) => {
    const width = 22 + ((row.value - min) / Math.max(max - min, 1)) * 78;
    const negative = row.value < horizonData("base_plan")[forecastKey()] ? "negative" : "";
    return `<div class="bar-row">
      <span class="bar-label" title="${row.label}">${row.label}</span>
      <div class="bar-track"><div class="bar-fill ${negative}" style="width:${width}%"></div></div>
      <span class="bar-value">${money(row.value, true)}</span>
    </div>`;
  }).join("");
}

function renderModelHealth() {
  const labels = { net_revenue_usd: "Net revenue", shipped_revenue_usd: "Shipped revenue" };
  document.querySelector("#model-health").innerHTML = Object.entries(dashboard.model_health).map(([target, model]) => `
    <article class="model-card">
      <header><h3>${labels[target]}</h3><span class="model-name">${titleCase(model.champion)}</span></header>
      <div class="metric-row">
        <div><span>13-week WAPE</span><strong>${model.wape_pct}%</strong></div>
        <div><span>Bias</span><strong>${model.bias_pct > 0 ? "+" : ""}${model.bias_pct}%</strong></div>
        <div><span>90% coverage</span><strong>${model.interval_coverage_pct}%</strong></div>
      </div>
    </article>`).join("");
}

function renderTable() {
  const base = horizonData("base_plan")[forecastKey()];
  const rows = dashboard.scenarios
    .map((item) => ({ ...item, metrics: item.horizons[`${state.horizon}_days`] }))
    .sort((a, b) => b.metrics[forecastKey()] - a.metrics[forecastKey()]);
  document.querySelector("#scenario-table").innerHTML = rows.map((row) => {
    const value = row.metrics[forecastKey()];
    const delta = value - base;
    const deltaClass = delta > 0 ? "delta-up" : delta < 0 ? "delta-down" : "";
    const capacity = row.assumptions.fulfillment_capacity_multiplier;
    return `<tr>
      <td><span class="scenario-name">${row.label}</span><span class="scenario-description">${row.description}</span></td>
      <td>${money(value)}</td>
      <td class="${deltaClass}">${delta === 0 ? "—" : signedMoney(delta)}</td>
      <td>${money(row.metrics.marketing_spend_usd)}</td>
      <td>${Math.round(capacity * 100)}%</td>
    </tr>`;
  }).join("");
}

function render() {
  updateControls();
  renderKpis();
  renderChart();
  renderScenarioBars();
  renderTable();
}

async function init() {
  const response = await fetch("data/dashboard.json");
  if (!response.ok) throw new Error("Dashboard data could not be loaded");
  dashboard = await response.json();
  document.querySelector("#data-status").textContent =
    `${dashboard.quality.data_gate} data gate · ${dashboard.quality.source_count} sources · ${dashboard.quality.forecast_ready_days.toLocaleString()} forecast-ready days`;
  document.querySelector("#as-of").textContent = dashboard.as_of_date;
  document.querySelector("#forecast-through").textContent = dashboard.forecast_end_date;
  document.querySelectorAll("[data-horizon]").forEach((button) => button.addEventListener("click", () => {
    state.horizon = Number(button.dataset.horizon);
    render();
  }));
  document.querySelectorAll("[data-target]").forEach((button) => button.addEventListener("click", () => {
    state.target = button.dataset.target;
    render();
  }));
  renderModelHealth();
  render();
}

init().catch((error) => {
  document.querySelector("#data-status").textContent = error.message;
  document.querySelector(".status-dot").style.background = "#ba4b47";
});
