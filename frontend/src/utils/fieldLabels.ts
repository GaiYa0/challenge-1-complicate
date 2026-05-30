export const FIELD_LABEL_MAP: Record<string, string> = {
  row: '序号',
  from_user: '付款方',
  to_user: '对手方',
  amount: '金额',
  timestamp: '交易时间',
  location: '地点',
  txn_time: '交易时间',
  time: '时间',
  trade_time: '交易时间',
  account: '账户',
  counterparty: '对手方',
  bank_card: '银行卡号',
  name: '户名',
  txn_type: '交易类型',
  tx_count: '交易笔数',
  total_amount: '总金额',
  earliest_time: '最早时间',
  latest_time: '最晚时间',
  phone: '手机号',
  id_card: '身份证号',
  latitude: '纬度',
  longitude: '经度',
  address: '地址',
  is_anomaly: '异常标记',
  anomaly_reason: '异常原因',
}

export function getFieldLabel(key: string): string {
  return FIELD_LABEL_MAP[key] ?? key
}
