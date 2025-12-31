export type LiveTraffic = {
  platform: string;
  category_name: string;
  viewers: number;
  top_streamers_detail: { name: string; title?: string; viewers?: number }[];
  ts_utc: string;
};

export type TrendPoint = {
  ts_utc: string;
  platform: string;
  viewers: number;
  top_streamers_detail: { name: string; title?: string; viewers?: number }[];
};

export type EventItem = {
  event_id: number;
  created_at: string;
  platform: string;
  category_name: string;
  event_type: string;
  growth_rate: number;
  cause_detail: Record<string, unknown> | string | null;
};

export type DailyTop = {
  platform: string;
  category_name: string;
  avg_viewers: number;
  peak_viewers: number;
};

export type FlashCategory = {
  platform: string;
  category_name: string;
  peak_viewers: number;
  active_days: number;
  peak_contributor: string;
  curr_viewers: number;
  current_broadcaster: string;
};

export type KingStreamer = {
  platform: string;
  category: string;
  streamer: string;
  title: string;
  viewers: number;
  timestamp: string;
};

export type NewCategory = {
  platform: string;
  category_name: string;
};

export type VolatilityMetric = {
  platform: string;
  category_name: string;
  avg_v: number;
  volatility_index: number;
};
