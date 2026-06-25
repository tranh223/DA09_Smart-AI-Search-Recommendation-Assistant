import { useEffect, useState, useMemo } from 'react';
import { t } from '../styles/theme';
import { useAuth } from '../hooks/useAuth';
import { NavBar } from '../components/layout/NavBar';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { getOverview, getDayAnalysis, getMonthAnalysis } from '../services/dashboardApi';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

export function Dashboard() {
  const { token } = useAuth();
  const [overview, setOverview] = useState<any>(null);
  const [month, setMonth] = useState<number>(new Date().getMonth() + 1);
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [dayData, setDayData] = useState<any>(null);
  const [monthData, setMonthData] = useState<any>(null);
  const unit: any = {'csat': '(%)', 'latency': '(ms)', 'ttft': '(ms)', 'hit rate': '(%)', 'input token': '', 'output token': ''}
  const current_year = new Date().getFullYear()

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const o = await getOverview(token);
        if (mounted) setOverview(o);
      } catch (e) {
        // ignore
      }
    }
    load();
    const id = setInterval(load, 15_000); // poll every 15s
    return () => { mounted = false; clearInterval(id); };
  }, [token]);

  useEffect(() => {
    let mounted = true;
    getDayAnalysis(month, token).then(d => mounted && setDayData(d)).catch(() => {});
    return () => { mounted = false; };
  }, [month, token]);

  useEffect(() => {
    let mounted = true;
    getMonthAnalysis(year, token).then(d => mounted && setMonthData(d)).catch(() => {});
    return () => { mounted = false; };
  }, [year, token]);

  const monthsLabels = useMemo(() => (monthData?.months ? monthData.months.map((m: number) => String(m)) : []), [monthData]);
  const daysLabels = useMemo(() => {
    if (!dayData) return [];
    return dayData.csat.map((_: any, i: number) => String(i + 1));
  }, [dayData]);

  function buildLine(labels: string[], datasets: any[]) {
    return { labels, datasets };
  }

  function metricDataset(values: number[], color: string, label: string) {
    return {
      label,
      data: values,
      borderColor: color,
      backgroundColor: color,
      tension: 0.25,
    };
  }

  function sparseRagas(valuesArr: number[] | undefined, dates: string[] | undefined) {
    // build per-day array aligned with daysLabels using dayData.ragas.date to locate which days have values
    if (!dayData || !dates || !valuesArr) return daysLabels.map(() => null);
    const map: Record<string, number | null> = {};
    for (let i = 0; i < dates.length; i++) {
      const d = dates[i];
      map[d] = valuesArr[i] ?? null;
    }
    return daysLabels.map((_: string, idx: number) => {
      const day = String(idx + 1).padStart(2, '0');
      const dateStr = `${new Date().getFullYear()}-${String(month).padStart(2, '0')}-${day}`;
      return map.hasOwnProperty(dateStr) ? map[dateStr] : null;
    });
  }
  return (
    <div style={{ fontFamily: t.font, background: t.bg, color: t.ink, minHeight: '100vh' }}>
      <NavBar showLinks={false} />
      <div style={{ padding: '30px 40px 0px 40px', display: 'flex', alignItems: 'center', gap: 24 }}>
        <div style={{ fontFamily: t.serif, fontSize: 22, fontWeight: 700 }}>Dashboard</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 12 }}>
          <select value={month} onChange={e => setMonth(Number(e.target.value))} style={{ padding: '8px 10px', borderRadius: 8, border: `1px solid ${t.border}` }}>
            {Array.from({ length: 12 }).map((_, i) => (
              <option key={i} value={i + 1}>{i + 1}</option>
            ))}
          </select>
          <select value={year} onChange={e => setYear(Number(e.target.value))} style={{ padding: '8px 10px', borderRadius: 8, border: `1px solid ${t.border}` }}>
            <option value={new Date().getFullYear()}>{new Date().getFullYear()}</option>
            <option value={new Date().getFullYear() - 1}>{new Date().getFullYear() - 1}</option>
          </select>
        </div>
      </div>

      <div style={{ padding: 24, display: 'grid', gap: 20 }}>
        {/* Top overview */}
        <div style={{ display: 'flex', gap: 16, alignItems: 'stretch' }}>
          {['csat', 'latency', 'ttft', 'hit rate', 'input token', 'output token'].map(key => (
            <div key={key} style={{ flex: 1, background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: 12, color: t.ink3, marginBottom: 8 }}>{key.toUpperCase()} today {unit[key]}</div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>{overview ? overview[key] : '—'}</div>
            </div>
          ))}
        </div>

        {/* Charts grid: each metric row has day(left 60%) and month(right 40%) */}
        <div style={{ display: 'grid', gap: 20 }}>
          {/** CSAT row **/}
          <div style={{ display: 'grid', gridTemplateColumns: '6fr 4fr', gap: 12 }}>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>CSAT (tháng {month}/{current_year})</div>
              <div style={{ height: 340 }}>
                {dayData && (
                  <Line options={{ scales: { x: { ticks: { maxRotation: 0, minRotation: 0 } } } }} data={buildLine(daysLabels, [metricDataset(dayData.csat, 'rgb(34,197,94)', 'CSAT (%)')])} />
                )}
              </div>
            </div>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>CSAT (năm {year})</div>
              <div style={{ height: 340 }}>
                {monthData && (
                  <Line options={{ maintainAspectRatio: false }} data={buildLine(monthsLabels, [metricDataset(monthData.csat, 'rgb(34,197,94)', 'CSAT (%)')])} />
                )}
              </div>
            </div>
          </div>

          {/** Latency row **/}
          <div style={{ display: 'grid', gridTemplateColumns: '6fr 4fr', gap: 12 }}>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Latency (tháng {month}/{current_year})</div>
              <div style={{ height: 340 }}>
                {dayData && (<Line options={{ scales: { x: { ticks: { maxRotation: 0, minRotation: 0 } } } }} data={buildLine(daysLabels, [metricDataset(dayData.latency, 'rgb(59,130,246)', 'Latency (ms)')])} />)}
              </div>
            </div>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Latency (năm {year})</div>
              <div style={{ height: 340 }}>
                {monthData && (<Line options={{ maintainAspectRatio: false }} data={buildLine(monthsLabels, [metricDataset(monthData.latency, 'rgb(59,130,246)', 'Latency (ms)')])} />)}
              </div>
            </div>
          </div>

          {/** TTFT row **/}
          <div style={{ display: 'grid', gridTemplateColumns: '6fr 4fr', gap: 12 }}>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Time To First Token (tháng {month}/{current_year})</div>
              <div style={{ height: 340 }}>
                {dayData && (<Line options={{ scales: { x: { ticks: { maxRotation: 0, minRotation: 0 } } } }} data={buildLine(daysLabels, [metricDataset(dayData.ttft, 'rgb(234,88,12)', 'TTFT (ms)')])} />)}
              </div>
            </div>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Time To First Token (năm {year})</div>
              <div style={{ height: 340 }}>
                {monthData && (<Line options={{ maintainAspectRatio: false }} data={buildLine(monthsLabels, [metricDataset(monthData.ttft, 'rgb(234,88,12)', 'TTFT (ms)')])} />)}
              </div>
            </div>
          </div>

          {/** Booking row **/}
          <div style={{ display: 'grid', gridTemplateColumns: '6fr 4fr', gap: 12 }}>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Hit rate (tháng {month}/{current_year})</div>
              <div style={{ height: 340 }}>
                {dayData && (<Line options={{ scales: { x: { ticks: { maxRotation: 0, minRotation: 0 } } } }} data={buildLine(daysLabels, [metricDataset(dayData.booking, 'rgb(168,85,247)', 'Booking (%)')])} />)}
              </div>
            </div>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Hit rate (năm {year})</div>
              <div style={{ height: 340 }}>
                {monthData && (<Line options={{ maintainAspectRatio: false }} data={buildLine(monthsLabels, [metricDataset(monthData.booking, 'rgb(168,85,247)', 'Booking (%)')])} />)}
              </div>
            </div>
          </div>
          {/** Tokens row: input/output tokens (day left + month right) */}
          <div style={{ display: 'grid', gridTemplateColumns: '6fr 4fr', gap: 12 }}>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Tokens (tháng {month}/{current_year})</div>
              <div style={{ height: 340 }}>
                {dayData && (
                  <Line options={{ scales: { x: { ticks: { maxRotation: 0, minRotation: 0 } } } }} data={buildLine(daysLabels, [
                    metricDataset(dayData.input_token, 'rgb(14,165,233)', 'Input Token'),
                    metricDataset(dayData.output_token, 'rgb(236,72,153)', 'Output Token'),
                  ])} />
                )}
              </div>
            </div>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Tokens (năm {year})</div>
              <div style={{ height: 340 }}>
                {monthData && (
                  <Line options={{ maintainAspectRatio: false }} data={buildLine(monthsLabels, [
                    metricDataset(monthData.input_token, 'rgb(14,165,233)', 'Input Token'),
                    metricDataset(monthData.output_token, 'rgb(236,72,153)', 'Output Token'),
                  ])} />
                )}
              </div>
            </div>
          </div>

          {/** Token cost row: input/output token cost (day left + month right) */}
          <div style={{ display: 'grid', gridTemplateColumns: '6fr 4fr', gap: 12 }}>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Token Cost (tháng {month}/{current_year})</div>
              <div style={{ height: 340 }}>
                {dayData && (
                  <Line options={{ scales: { x: { ticks: { maxRotation: 0, minRotation: 0 } } } }} data={buildLine(daysLabels, [
                    metricDataset(dayData.input_token_cost, 'rgb(34,197,94)', 'Input Token Cost'),
                    metricDataset(dayData.output_token_cost, 'rgb(59,130,246)', 'Output Token Cost'),
                  ])} />
                )}
              </div>
            </div>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Token Cost (năm {year})</div>
              <div style={{ height: 340 }}>
                {monthData && (
                  <Line options={{ maintainAspectRatio: false }} data={buildLine(monthsLabels, [
                    metricDataset(monthData.input_token_cost, 'rgb(34,197,94)', 'Input Token Cost'),
                    metricDataset(monthData.output_token_cost, 'rgb(59,130,246)', 'Output Token Cost'),
                  ])} />
                )}
              </div>
            </div>
          </div>

          {/** RAGAS row: day (left) + month (right) */}
          <div style={{ display: 'grid', gridTemplateColumns: '6fr 4fr', gap: 12 }}>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>RAGAS (tháng {month}/{current_year})</div>
              <div style={{ height: 340 }}>
                {dayData && (
                  <Line options={{ scales: { x: { ticks: { maxRotation: 0, minRotation: 0 } } } }} data={buildLine(daysLabels, [
                    metricDataset(sparseRagas(dayData.ragas?.faithfulness, dayData.ragas?.date), 'rgb(34,197,94)', 'Faithfulness'),
                    metricDataset(sparseRagas(dayData.ragas?.answer_relevance, dayData.ragas?.date), 'rgb(59,130,246)', 'Answer Relevance'),
                    metricDataset(sparseRagas(dayData.ragas?.context_precision, dayData.ragas?.date), 'rgb(234,88,12)', 'Context Precision'),
                  ])} />
                )}
              </div>
            </div>
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>RAGAS (năm {year})</div>
              <div style={{ height: 340 }}>
                {monthData && (
                  <Line options={{ maintainAspectRatio: false }} data={buildLine(monthsLabels, [
                    metricDataset(monthData.ragas.faithfulness, 'rgb(34,197,94)', 'Faithfulness'),
                    metricDataset(monthData.ragas.answer_relevance, 'rgb(59,130,246)', 'Answer Relevance'),
                    metricDataset(monthData.ragas.context_precision, 'rgb(234,88,12)', 'Context Precision'),
                  ])} />
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
