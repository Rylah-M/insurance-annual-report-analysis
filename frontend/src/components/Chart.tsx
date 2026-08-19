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
  unit
}: {
  title: string;
  x: Array<string | number>;
  y: Array<number | null>;
  unit?: string | null;
}) {
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
        series: [
          {
            type: "line",
            data: y,
            smooth: true,
            symbolSize: 8,
            lineStyle: { color: "#0f766e", width: 3 },
            itemStyle: { color: "#0f766e" },
            areaStyle: { color: "rgba(15, 118, 110, 0.12)" }
          }
        ]
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
