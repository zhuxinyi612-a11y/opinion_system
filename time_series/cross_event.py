"""
跨事件因果分析 (Cross-Event Granger Causality)
==============================================
用格兰杰因果检验发现事件之间的影响关系。

核心问题：事件A的情绪变化，是否在 N 小时后引起了事件B的报道量变化？

理论：VAR 模型 + 格兰杰因果检验（Granger, 1969）
  - 不是"相关性"，是"时序上的预测能力"
  - 如果加入事件A的过去值能显著提升对事件B当前值的预测精度，
    则 A 格兰杰导致了 B

使用方式：
    from time_series.cross_event import CrossEventAnalyzer
    analyzer = CrossEventAnalyzer()
    result = analyzer.analyze(events_dict)
"""

from __future__ import annotations

from typing import Any

import numpy as np


class CrossEventAnalyzer:
    """
    跨事件因果分析器

    输入：多个事件的时间序列数据
    输出：事件对之间的格兰杰因果方向和强度
    """

    def __init__(self, max_lag: int = 6, significance_level: float = 0.05):
        """
        max_lag: 最大滞后阶数（小时），检验"过去 N 小时内的影响"
        significance_level: 显著性阈值
        """
        self.max_lag = max_lag
        self.significance_level = significance_level

    def analyze(
        self,
        events: dict[str, list[dict[str, Any]]],
        target_field: str = "news_count",
        driver_field: str = "negative_ratio",
    ) -> dict[str, Any]:
        """
        主入口：对所有事件对做格兰杰因果检验

        参数：
          events: {event_id: [records]} 字典
                 每个 record = {"time": datetime, "news_count": int, "sentiment_*": float, ...}
          target_field:   作为"被影响"的变量（默认报道量）
          driver_field:   作为"施加影响"的变量（默认负面情绪占比）

        返回：
          {
            "pairs": [ {from, to, best_lag, p_value, is_significant, interpretation}, ... ],
            "causal_graph": {A: [B, C], B: [C]},  # 有向因果边
            "summary": "发现了 2 对显著因果关系"
          }
        """
        event_ids = list(events.keys())
        n_events = len(event_ids)

        if n_events < 2:
            return {"pairs": [], "causal_graph": {}, "summary": "需要至少 2 个事件才能做跨事件分析"}

        # 提取每个事件的时序
        event_series = {}
        for eid in event_ids:
            driver_vals = [r.get(driver_field, 0) for r in events[eid]]
            target_vals = [r.get(target_field, 0) for r in events[eid]]
            event_series[eid] = {
                "driver": np.array(driver_vals),
                "target": np.array(target_vals),
                "title": events[eid][0].get("event_title", eid) if events[eid] else eid,
            }

        # 对每一对事件做格兰杰检验
        pairs = []
        causal_graph: dict[str, list[str]] = {eid: [] for eid in event_ids}

        for i in range(n_events):
            for j in range(n_events):
                if i == j:
                    continue

                eid_a = event_ids[i]
                eid_b = event_ids[j]

                result = self._granger_test(
                    driver_series=event_series[eid_a]["driver"],
                    target_series=event_series[eid_b]["target"],
                    max_lag=self.max_lag,
                )

                if result is None:
                    continue

                best_lag, best_pvalue, all_pvalues = result

                is_sig = best_pvalue < self.significance_level

                if is_sig:
                    causal_graph[eid_a].append(eid_b)

                pairs.append({
                    "from_event": eid_a,
                    "from_title": event_series[eid_a]["title"],
                    "to_event": eid_b,
                    "to_title": event_series[eid_b]["title"],
                    "driver_field": driver_field,
                    "target_field": target_field,
                    "best_lag_hours": best_lag,
                    "p_value": round(best_pvalue, 4),
                    "is_significant": is_sig,
                    "all_lag_pvalues": {str(k): round(v, 4) for k, v in all_pvalues.items()},
                    "interpretation": self._make_interpretation(
                        event_series[eid_a]["title"], driver_field,
                        event_series[eid_b]["title"], target_field,
                        best_lag, best_pvalue, is_sig,
                    ),
                })

        # 按 p 值排序（最显著的排前面）
        pairs.sort(key=lambda p: p["p_value"])

        significant_count = sum(1 for p in pairs if p["is_significant"])

        return {
            "pairs": pairs,
            "causal_graph": {k: v for k, v in causal_graph.items() if v},
            "significant_pairs": significant_count,
            "total_pairs_tested": len(pairs),
            "summary": (
                f"在 {len(pairs)} 对事件中发现了 {significant_count} 对显著因果关系 "
                f"(p < {self.significance_level})。"
                if significant_count > 0
                else f"在 {len(pairs)} 对事件中未发现显著因果关系。"
            ),
            "method": f"格兰杰因果检验 (Granger, 1969), max_lag={self.max_lag}h, alpha={self.significance_level}",
        }

    # ---------- 内部方法 ----------

    def _granger_test(
        self,
        driver_series: np.ndarray,
        target_series: np.ndarray,
        max_lag: int = 6,
    ) -> tuple[int, float, dict[int, float]] | None:
        """
        对两个序列做格兰杰因果检验

        H0: driver 的过去值对预测 target 的当前值没有额外帮助

        对每个 lag ∈ [1, max_lag] 做 F 检验，返回最优 lag 和对应的 p 值。

        手写实现（不依赖 statsmodels），核心是两个 OLS 回归的残差平方和比：

          restricted:   target[t] = a0 + a1*target[t-1] + ... + aL*target[t-L]
          unrestricted: target[t] = b0 + b1*target[t-1] + ... + bL*target[t-L]
                                    + c1*driver[t-1]  + ... + cL*driver[t-L]

          F = ((RSS_r - RSS_u) / L) / (RSS_u / (n - 2L - 1))
        """
        n = len(target_series)
        if n < 2 * max_lag + 2:
            return None  # 数据太少

        best_lag = 1
        best_pvalue = 1.0
        all_pvalues: dict[int, float] = {}

        for lag in range(1, max_lag + 1):
            if n - lag < 10:
                break

            # 构建回归矩阵
            y = target_series[lag:]  # 被预测值
            m = len(y)

            # 受限模型 (restricted): 只用 target 的历史
            X_r = np.zeros((m, lag + 1))
            X_r[:, 0] = 1.0  # 截距
            for k in range(lag):
                X_r[:, k + 1] = target_series[lag - k - 1: n - k - 1]

            # 非受限模型 (unrestricted): target 历史 + driver 历史
            X_u = np.zeros((m, 2 * lag + 1))
            X_u[:, 0] = 1.0
            for k in range(lag):
                X_u[:, k + 1] = target_series[lag - k - 1: n - k - 1]
            for k in range(lag):
                X_u[:, lag + 1 + k] = driver_series[lag - k - 1: n - k - 1]

            # OLS 拟合
            beta_r = self._ols(X_r, y)
            beta_u = self._ols(X_u, y)

            if beta_r is None or beta_u is None:
                continue

            # 残差平方和
            y_pred_r = X_r @ beta_r
            y_pred_u = X_u @ beta_u
            rss_r = float(np.sum((y - y_pred_r) ** 2))
            rss_u = float(np.sum((y - y_pred_u) ** 2))

            if rss_u < 1e-10:
                p_value = 0.0  # 完美拟合
            elif rss_u >= rss_r:
                p_value = 1.0  # driver 没有提供额外信息
            else:
                # F 统计量
                df1 = lag           # 分子自由度
                df2 = m - 2 * lag - 1  # 分母自由度
                if df2 <= 0:
                    continue
                f_stat = ((rss_r - rss_u) / df1) / (rss_u / df2)

                # F 分布的 p 值（用 Beta 不完全函数近似）
                p_value = self._f_pvalue(max(0, f_stat), df1, df2)

            all_pvalues[lag] = p_value

            if p_value < best_pvalue:
                best_pvalue = p_value
                best_lag = lag

        return best_lag, best_pvalue, all_pvalues

    @staticmethod
    def _ols(X: np.ndarray, y: np.ndarray) -> np.ndarray | None:
        """最小二乘回归 X @ beta = y"""
        try:
            # beta = (X^T X)^-1 X^T y
            XtX = X.T @ X
            Xty = X.T @ y
            beta = np.linalg.solve(XtX, Xty)
            return beta
        except np.linalg.LinAlgError:
            # 奇异矩阵，用伪逆
            try:
                return np.linalg.pinv(XtX) @ Xty
            except Exception:
                return None

    @staticmethod
    def _f_pvalue(f_stat: float, df1: int, df2: int) -> float:
        """F 分布右尾 p 值（Beta 正则化不完全函数近似）"""
        if f_stat <= 0:
            return 1.0
        from math import exp, lgamma, log

        x = df2 / (df2 + df1 * f_stat)
        a = df2 / 2.0
        b = df1 / 2.0

        # 正则化不完全 Beta 函数（连分式展开近似）
        def betai(x, a, b):
            if x <= 0:
                return 0.0
            if x >= 1:
                return 1.0

            # 连分式展开
            def cont_frac(x, a, b):
                itmax = 200
                eps = 3e-15
                fpmin = 1e-30

                qab = a + b
                qap = a + 1.0
                qam = a - 1.0
                c = 1.0
                d = 1.0 - qab * x / qap
                if abs(d) < fpmin:
                    d = fpmin
                d = 1.0 / d
                h = d

                for m in range(1, itmax + 1):
                    m2 = 2 * m
                    aa = m * (b - m) * x / ((qam + m2) * (a + m2))
                    d = 1.0 + aa * d
                    if abs(d) < fpmin:
                        d = fpmin
                    c = 1.0 + aa / c
                    if abs(c) < fpmin:
                        c = fpmin
                    d = 1.0 / d
                    h *= d * c
                    aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
                    d = 1.0 + aa * d
                    if abs(d) < fpmin:
                        d = fpmin
                    c = 1.0 + aa / c
                    if abs(c) < fpmin:
                        c = fpmin
                    d = 1.0 / d
                    del_ = d * c
                    h *= del_
                    if abs(del_ - 1.0) < eps:
                        break

                return h

            # Beta(a,b)
            beta_ab = exp(lgamma(a) + lgamma(b) - lgamma(a + b))
            front = (x ** a) * ((1.0 - x) ** b) / a / beta_ab
            return front * cont_frac(x, a, b)

        return 1.0 - betai(x, a, b)

    @staticmethod
    def _make_interpretation(
        from_title: str, driver_field: str,
        to_title: str, target_field: str,
        best_lag: int, p_value: float, is_sig: bool,
    ) -> str:
        """生成人类可读的解释文本"""
        field_name = {
            "negative_ratio": "负面情绪",
            "positive_ratio": "正面情绪",
            "news_count": "报道量",
        }
        driver_cn = field_name.get(driver_field, driver_field)
        target_cn = field_name.get(target_field, target_field)

        if is_sig:
            return (
                f"「{from_title}」的{driver_cn}变化在 {best_lag} 小时后"
                f"显著影响「{to_title}」的{target_cn}"
                f"（p={p_value:.4f}）。"
            )
        else:
            return (
                f"「{from_title}」的{driver_cn}与「{to_title}」的{target_cn}"
                f"之间未发现显著时序因果关系（最低p={p_value:.4f}）。"
            )


# ====== 自测 ======
if __name__ == "__main__":
    from time_series.utils.mock_data import generate_mock_events

    print("=" * 60)
    print("跨事件格兰杰因果分析 — 自测")
    print("=" * 60)

    events_raw = generate_mock_events(num_events=3)

    # 构造 events 字典
    events = {}
    for evt in events_raw:
        eid = evt["event_id"]
        # 给每个 record 加上 event_title
        for r in evt["timeseries"]:
            r["event_title"] = evt["event_title"]
        events[eid] = evt["timeseries"]

    analyzer = CrossEventAnalyzer(max_lag=6, significance_level=0.05)
    result = analyzer.analyze(events)

    print(f"\n{result['summary']}")
    print(f"方法: {result['method']}\n")

    print("事件对分析结果:")
    for p in result["pairs"]:
        sig = "*** 显著 ***" if p["is_significant"] else ""
        print(f"\n  {p['from_title']} → {p['to_title']}  {sig}")
        print(f"    最佳滞后: {p['best_lag_hours']}h | p={p['p_value']:.4f}")
        print(f"    各滞后p值: {p['all_lag_pvalues']}")
        print(f"    {p['interpretation']}")

    if result["causal_graph"]:
        print(f"\n因果图 (有向边 A→B = A的driver Granger-cause B的target):")
        for src, targets in result["causal_graph"].items():
            for tgt in targets:
                src_title = events[src][0].get("event_title", src) if events[src] else src
                tgt_title = events[tgt][0].get("event_title", tgt) if events[tgt] else tgt
                print(f"  {src_title} → {tgt_title}")
