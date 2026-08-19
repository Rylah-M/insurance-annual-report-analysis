import ReactECharts from "echarts-for-react";

export function BarChart({
  title,
  x,
  y,
  unit
}: {
  title: string;
  x: Array<string | number>;
  y: Array<number | null>;
  unit?: string | null;
}) {
  return (
    <ReactECharts
      style={{ height: 320 }}
      option={{
        title: { text: title, textStyle: { fontSize: 14, fontWeight: 600 } },
        tooltip: {
          trigger: "axis",
          valueFormatter: (value: number) => `${value}${unit ?? ""}`
        },
        grid: { left: 48, right: 24, top: 54, bottom: 42 },
        xAxis: { type: "category", data: x },
        yAxis: { type: "value" },
        series: [
          {
            type: "bar",
            data: y,
            itemStyle: { color: "#1f6feb", borderRadius: [4, 4, 0, 0] }
          }
        ]
      }}
    />
  );
}

export function LineChart({
  title,
  x,
  y,
  unit,
  series
}: {
  title: string;
  x: Array<string | number>;
  y: Array<number | null>;
  unit?: string | null;
  series?: Array<{ name: string; data: Array<number | null> }>;
}) {
  const colors = ["#0f766e", "#1f6feb", "#f59e0b", "#64748b"];
  const lines =
    series && series.length
      ? series.map((item, index) => ({
          ...item,
          color: colors[index % colors.length]
        }))
      : [{ name: "", data: y, color: colors[0] }];
  return (
    <ReactECharts
      style={{ height: 280 }}
      option={{
        title: { text: title, textStyle: { fontSize: 14, fontWeight: 600 } },
        tooltip: {
          trigger: "axis",
          valueFormatter: (value: number) => `${value}${unit ?? ""}`
        },
        grid: { left: 48, right: 24, top: 54, bottom: 42 },
        xAxis: { type: "category", data: x },
        yAxis: { type: "value" },
        legend: lines.length > 1 ? { top: 4, right: 8 } : undefined,
        series: lines.map((line) => ({
            type: "line",
            name: line.name,
            data: line.data,
            smooth: true,
            connectNulls: true,
            symbolSize: 8,
            lineStyle: { color: line.color, width: 3 },
            itemStyle: { color: line.color },
            areaStyle:
              lines.length === 1
                ? { color: "rgba(15, 118, 110, 0.12)" }
                : undefined
          }))
      }}
    />
  );
}

export function PieChart({
  title,
  data,
  unit
}: {
  title: string;
  data: Array<{ name: string; value: number }>;
  unit?: string | null;
}) {
  return (
    <ReactECharts
      style={{ height: 280 }}
      option={{
        title: { text: title, textStyle: { fontSize: 14, fontWeight: 600 } },
        tooltip: {
          trigger: "item",
          valueFormatter: (value: number) => `${value}${unit ?? ""}`
        },
        legend: { bottom: 0 },
        series: [
          {
            type: "pie",
            radius: ["42%", "68%"],
            center: ["50%", "48%"],
            data,
            color: ["#1f6feb", "#0f766e", "#f59e0b", "#64748b"],
            label: { formatter: "{b}: {d}%" }
          }
        ]
      }}
    />
  );
}
