// 0.1 分发精简开关：关掉的功能在前端隐藏（导航 + 视图 + 深链 + 落地页/首屏 CTA），
// 代码完整保留、未删除。把对应项改成 true，重新 build 部署即可一键恢复。详见 README。
export const FEATURES = {
  portfolio: false, // 持仓 / IBKR 提案式交易 / 价格提醒
  quant: false,     // 量化组合
  ashare: false,    // 低波蓝筹（A股 smart-beta）
  record: false,    // 公开成绩单（需积累半年才出对账，0.1 暂收起）
}
