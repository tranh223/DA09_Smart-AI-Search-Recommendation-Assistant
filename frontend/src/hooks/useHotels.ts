import { useEffect, useState } from 'react';
import { listHotels, type Hotel, type HotelListParams } from '../services/hotels';

interface State {
  hotels: Hotel[];
  total: number;
  loading: boolean;
  error: string | null;
}

export function useHotels(params: HotelListParams = {}) {
  const [state, setState] = useState<State>({ hotels: [], total: 0, loading: true, error: null });
  const key = JSON.stringify(params);

  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    listHotels(params)
      .then((res) => {
        if (alive) setState({ hotels: res.hotels, total: res.total, loading: false, error: null });
      })
      .catch((err) => {
        if (alive) setState({ hotels: [], total: 0, loading: false, error: err?.message ?? 'Lỗi tải dữ liệu' });
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state;
}
