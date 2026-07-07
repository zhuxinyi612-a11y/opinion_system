"""
事件传播溯源 & 传播路径构建
=========================
v2.0: networkx DiGraph 替换嵌套字典树

核心改动：
  - 旧：嵌套 dict 树结构（一个节点只能有一个父节点，有向图当成树）
  - 新：networkx DiGraph（支持多父节点，传播本质是有向无环图不是树）
  - 旧：关键节点判断只看粉丝数
  - 新：用 PageRank + 介数中心性 + 出度 三维图算法

数据输入来源：
  - 1号爬虫：转发关系链、账号粉丝数
  - 3号NLP： 事件聚合结果（哪些文章属于同一事件）
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import networkx as nx


class PropagationTracer:
    """
    传播链路分析器 v2.0

    使用方式：
        tracer = PropagationTracer()
        result = tracer.analyze(propagation_nodes)
    """

    def __init__(
        self,
        influencer_threshold: int = 100_000,
        official_keywords: tuple[str, ...] = ("官方", "发布", "日报", "新闻", "央视", "新华", "人民"),
    ):
        self.influencer_threshold = influencer_threshold
        self.official_keywords = official_keywords

    # ================================================================
    #  主入口
    # ================================================================

    def analyze(self, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """
        主入口：分析传播链路

        参数 nodes 格式（来自1号爬虫）：
          [
            {
              "node_id": "N001",
              "account_name": "...",
              "follower_count": 200,
              "is_verified": False,
              "post_time": datetime,
              "source": "新浪新闻",
              "parent_node_id": null 或 上级节点ID,
              "forward_count": 15,
              "title": "..."
            },
            ...
          ]

        返回：
          {
            "source_nodes": [...],          # 所有源头节点
            "key_nodes": [...],             # 图算法识别的关键节点
            "propagation_graph": {...},     # networkx 图分析结果
            "propagation_depth": 5,         # 最长传播链深度
            "total_reach": {...},           # 去重触达
            "timeline": [...],              # 时间线
            "graph_for_visualization": {...}, # 前端可视化数据
            "orphan_nodes": [...],          # 孤立节点
            "data_quality": {...},          # 数据质量
          }
        """
        if not nodes:
            return {"error": "没有传播数据"}

        # Step 1: 建图
        G, orphan_info = self._build_graph(nodes)

        # Step 2: 找源头（入度为0的节点）
        source_nodes = self._find_sources(G)

        # Step 3: 图算法识别关键节点
        key_nodes = self._find_key_nodes_graph(G, nodes)

        # Step 4: 最长传播链深度
        depth = self._calc_graph_depth(G)

        # Step 5: 去重触达
        total_reach = self._calc_total_reach(nodes)

        # Step 6: 时间线
        timeline = self._build_timeline(nodes)

        # Step 7: 前端可视化数据
        graph_viz = self._build_graph_for_viz(G, nodes)

        # Step 8: 图统计信息
        graph_stats = self._graph_stats(G)

        # Step 9: 反事实推演 — 每个关键节点的因果影响力
        counterfactual = self._counterfactual_analysis(G, key_nodes, nodes)

        return {
            "source_nodes": source_nodes,
            "key_nodes": key_nodes,
            "propagation_graph": graph_stats,
            "propagation_depth": depth,
            "total_reach": total_reach,
            "timeline": timeline,
            "graph_for_visualization": graph_viz,
            "orphan_nodes": orphan_info["orphans"],
            "counterfactual_analysis": counterfactual,
            "data_quality": {
                "total_nodes": len(nodes),
                "orphan_count": len(orphan_info["orphans"]),
                "is_complete": len(orphan_info["orphans"]) == 0,
                "graph_type": "networkx.DiGraph",
                "is_dag": orphan_info["is_dag"],
                "edge_count": G.number_of_edges(),
            },
        }

    # ================================================================
    #  建图
    # ================================================================

    def _build_graph(
        self, nodes: list[dict[str, Any]]
    ) -> tuple[nx.DiGraph, dict[str, Any]]:
        """
        构建有向传播图

        和旧版树结构的区别：
          - 一个节点可以有多个入边（被多人转发）
          - 环检测（传播不应该有环，但数据可能有）
          - 每个节点携带完整的属性数据

        返回：(G, orphan_info)
        """
        G = nx.DiGraph()
        orphans = []

        for n in nodes:
            G.add_node(
                n["node_id"],
                account_name=n["account_name"],
                follower_count=n.get("follower_count", 0),
                is_verified=n.get("is_verified", False),
                post_time=n["post_time"],
                source=n.get("source", ""),
                forward_count=n.get("forward_count", 0),
                title=n.get("title", ""),
            )

        # 加边
        all_ids = {n["node_id"] for n in nodes}
        for n in nodes:
            pid = n.get("parent_node_id")
            if pid is None:
                continue
            if pid in all_ids:
                G.add_edge(pid, n["node_id"])
            else:
                orphans.append({
                    "node_id": n["node_id"],
                    "account_name": n["account_name"],
                    "missing_parent_id": pid,
                    "source": n.get("source", ""),
                    "post_time": n["post_time"].strftime("%Y-%m-%d %H:%M") if isinstance(n["post_time"], datetime) else str(n["post_time"]),
                })

        is_dag = nx.is_directed_acyclic_graph(G)

        orphan_info = {
            "orphans": orphans,
            "is_dag": is_dag,
        }
        return G, orphan_info

    # ================================================================
    #  图分析
    # ================================================================

    def _find_sources(self, G: nx.DiGraph) -> list[dict[str, Any]]:
        """找源头：入度为0的节点"""
        sources = []
        for node_id in G.nodes():
            if G.in_degree(node_id) == 0:
                attr = G.nodes[node_id]
                t = attr.get("post_time")
                sources.append({
                    "node_id": node_id,
                    "account_name": attr["account_name"],
                    "post_time": t.strftime("%Y-%m-%d %H:%M") if isinstance(t, datetime) else str(t),
                    "source": attr["source"],
                    "follower_count": attr["follower_count"],
                    "title": attr.get("title", ""),
                })
        # 按时间排序
        sources.sort(key=lambda s: s["post_time"])
        return sources

    def _find_key_nodes_graph(
        self, G: nx.DiGraph, nodes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        用图算法识别关键传播节点

        三维度：
          1. PageRank — 全局影响力（考虑了邻居的重要性，不只是粉丝数）
          2. 介数中心性 (betweenness) — 桥接作用（信息传递经过它的比例）
          3. 出度 — 直接引爆能力（它转发给了多少人）

        综合排名前 N 的节点为关键节点。
        """
        n_nodes = G.number_of_nodes()
        if n_nodes == 0:
            return []

        # 计算三个指标
        pagerank = nx.pagerank(G, weight="forward_count")
        try:
            betweenness = nx.betweenness_centrality(G)
        except Exception:
            betweenness = {nid: 0.0 for nid in G.nodes()}

        out_degree = {nid: float(G.out_degree(nid)) for nid in G.nodes()}

        # 归一化到 [0, 1]
        def _normalize(d: dict) -> dict:
            mx = max(d.values()) if d else 1.0
            return {k: v / mx if mx > 0 else 0.0 for k, v in d.items()}

        pr_norm = _normalize(pagerank)
        bc_norm = _normalize(betweenness)
        od_norm = _normalize(out_degree)

        # 综合得分 = 0.45*PageRank + 0.35*介数 + 0.20*出度
        composite: dict[str, float] = {}
        for nid in G.nodes():
            composite[nid] = 0.45 * pr_norm[nid] + 0.35 * bc_norm[nid] + 0.20 * od_norm[nid]

        # 取排名前 40% 或至少前 3 个
        top_n = max(3, int(n_nodes * 0.4))
        sorted_nodes = sorted(composite.items(), key=lambda x: x[1], reverse=True)
        top_ids = {nid for nid, _ in sorted_nodes[:top_n]}

        # 为每个关键节点标注角色
        key_nodes = []
        for n in nodes:
            nid = n["node_id"]
            if nid not in top_ids:
                continue

            # 自动判定角色（三种信号结合）
            role = self._classify_node_role(n, G, pr_norm[nid], bc_norm[nid], od_norm[nid])

            t = n.get("post_time")
            key_nodes.append({
                "node_id": nid,
                "account_name": n["account_name"],
                "role": role,
                "follower_count": n.get("follower_count", 0),
                "forward_count": n.get("forward_count", 0),
                "post_time": t.strftime("%Y-%m-%d %H:%M") if isinstance(t, datetime) else str(t),
                "source": n.get("source", ""),
                "graph_scores": {
                    "pagerank": round(pr_norm.get(nid, 0), 4),
                    "betweenness": round(bc_norm.get(nid, 0), 4),
                    "out_degree_score": round(od_norm.get(nid, 0), 4),
                    "composite": round(composite[nid], 4),
                },
            })

        key_nodes.sort(key=lambda k: composite[k["node_id"]], reverse=True)
        return key_nodes

    def _classify_node_role(
        self, n: dict[str, Any], G: nx.DiGraph,
        pr_score: float, bc_score: float, od_score: float,
    ) -> str:
        """根据图指标分类节点角色"""
        nid = n["node_id"]
        # 源头
        if G.in_degree(nid) == 0:
            return "初始爆料源"

        # 桥接节点：介数中心性高，连接不同传播分支
        if bc_score > 0.5:
            return "跨平台/跨圈桥接节点"

        # 超级传播者：PageRank + 高出度
        if pr_score > 0.6:
            return "超级传播节点"

        # 官方媒体
        if self._is_official_account(n["account_name"]):
            return "官方媒体介入"

        # 认证大V
        if n.get("is_verified") and n.get("follower_count", 0) >= self.influencer_threshold:
            return "认证大V转发"

        # 高转发引爆点
        if n.get("forward_count", 0) >= 1000:
            return "高转发引爆点"

        # 结构重要节点
        if pr_score > 0.3:
            return "重要传播节点"

        return "传播参与者"

    def _calc_graph_depth(self, G: nx.DiGraph) -> int:
        """
        计算最长传播链深度

        用拓扑排序 + 动态规划求 DAG 最长路径
        如果不是 DAG，用 BFS 从源头出发求最长路径
        """
        n = G.number_of_nodes()
        if n == 0:
            return 0

        try:
            # DAG 最长路径
            return int(nx.dag_longest_path_length(G)) + 1
        except nx.NetworkXUnfeasible:
            # 不是 DAG（有环），用 BFS 估算
            sources = [nid for nid in G.nodes() if G.in_degree(nid) == 0]
            if not sources:
                # 全是环中节点，任意取一个
                sources = [list(G.nodes())[0]]

            max_depth = 0
            for src in sources:
                lengths = nx.single_source_shortest_path_length(G, src)
                max_depth = max(max_depth, max(lengths.values()) if lengths else 0)
            return max_depth + 1

    def _graph_stats(self, G: nx.DiGraph) -> dict[str, Any]:
        """图结构统计"""
        n = G.number_of_nodes()
        e = G.number_of_edges()
        return {
            "node_count": n,
            "edge_count": e,
            "is_dag": nx.is_directed_acyclic_graph(G),
            "density": round(nx.density(G), 4) if n > 1 else 0.0,
            "avg_in_degree": round(sum(d for _, d in G.in_degree()) / max(n, 1), 2),
            "avg_out_degree": round(sum(d for _, d in G.out_degree()) / max(n, 1), 2),
            "source_count": sum(1 for nid in G.nodes() if G.in_degree(nid) == 0),
            "sink_count": sum(1 for nid in G.nodes() if G.out_degree(nid) == 0),
            # 连通分量数
            "weakly_connected_components": nx.number_weakly_connected_components(G),
        }

    # ================================================================
    #  反事实推演（因果影响力）
    # ================================================================

    def _counterfactual_analysis(
        self, G: nx.DiGraph, key_nodes: list[dict[str, Any]],
        nodes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        反事实推演：量化每个关键节点的因果影响力

        方法：对每个关键节点，模拟"如果这个节点不存在"的假想场景：
          1. 从图中移除该节点
          2. 重新计算下游受影响节点数（无法从源头到达的节点）
          3. 计算损失的触达量（受影响节点的粉丝数之和）

        这就是该节点的**因果影响力**——不是 PageRank 或粉丝数，
        而是它实际造成的传播增量。

        答辩时：
          "我不只看谁粉丝多——我做反事实推演。删掉这个节点，
           如果传播规模从765万人降到200万人，说明这565万都是
           因为它的存在才发生的。这才是它的真正影响力。"
        """
        if G.number_of_nodes() == 0:
            return {"nodes_analyzed": 0, "results": []}

        # 找出所有源头节点（入度为0）
        sources = [nid for nid in G.nodes() if G.in_degree(nid) == 0]
        n_total = G.number_of_nodes()

        # 基线：完整图的所有可到达节点数
        baseline_reachable = set()
        for src in sources:
            try:
                descendants = nx.descendants(G, src) | {src}
                baseline_reachable.update(descendants)
            except Exception:
                pass
        baseline_count = len(baseline_reachable)
        baseline_reach = sum(
            G.nodes[nid].get("follower_count", 0)
            for nid in baseline_reachable
        )

        # 对每个关键节点做反事实推演
        results = []
        for kn in key_nodes:
            nid = kn["node_id"]
            if nid not in G.nodes():
                continue

            # 创建移除该节点后的子图
            G_cf = G.copy()
            G_cf.remove_node(nid)

            # 重新计算可到达节点
            cf_sources = [s for s in sources if s != nid and s in G_cf.nodes()]
            cf_reachable = set()
            for src in cf_sources:
                try:
                    descendants = nx.descendants(G_cf, src) | {src}
                    cf_reachable.update(descendants)
                except Exception:
                    pass
            cf_count = len(cf_reachable)
            cf_reach = sum(
                G_cf.nodes[n].get("follower_count", 0)
                for n in cf_reachable if n in G_cf.nodes()
            )

            # 因果效应
            lost_nodes = baseline_count - cf_count
            lost_reach = baseline_reach - cf_reach
            impact_ratio = lost_reach / max(baseline_reach, 1)

            results.append({
                "node_id": nid,
                "account_name": kn["account_name"],
                "follower_count": kn["follower_count"],
                "graph_role": kn["role"],
                "causal_impact": {
                    "nodes_lost_if_removed": lost_nodes,
                    "reach_lost_if_removed": lost_reach,
                    "impact_ratio": round(impact_ratio, 4),
                    "baseline_total_reach": baseline_reach,
                },
                "interpretation": (
                    f"若去掉{kn['account_name']}，传播触达从{baseline_reach:,}降至"
                    f"{cf_reach:,}，损失{lost_reach:,}人次({impact_ratio:.1%})。"
                    f"这才是它的真实因果贡献。"
                ),
            })

        # 按因果影响力排序
        results.sort(key=lambda r: r["causal_impact"]["impact_ratio"], reverse=True)

        # 汇总
        top_causal = results[0] if results else None

        return {
            "baseline": {
                "reachable_nodes": baseline_count,
                "total_reach": baseline_reach,
            },
            "nodes_analyzed": len(results),
            "top_causal_node": {
                "node_id": top_causal["node_id"],
                "account_name": top_causal["account_name"],
                "impact_ratio": top_causal["causal_impact"]["impact_ratio"],
            } if top_causal else None,
            "results": results,
            "method": "反事实推演：移除节点 → 计算下游损失 → 量化因果影响力",
        }

    # ================================================================
    #  辅助方法（保留旧版逻辑，兼容已有代码）
    # ================================================================

    def _is_official_account(self, name: str) -> bool:
        return any(kw in name for kw in self.official_keywords)

    def _calc_total_reach(self, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """去重触达估算（与旧版 #5 修复一致）"""
        if not nodes:
            return {"estimated_unique_reach": 0}

        SAME_PLATFORM_OVERLAP = 0.40
        AVG_FORWARD_EXPOSURE = 50

        platforms: dict[str, list[dict[str, Any]]] = {}
        for n in nodes:
            plat = n.get("source", "未知")
            platforms.setdefault(plat, []).append(n)

        reach_by_platform: dict[str, dict[str, Any]] = {}
        total_unique = 0

        for plat, plat_nodes in platforms.items():
            sorted_nodes = sorted(plat_nodes, key=lambda n: n["follower_count"], reverse=True)
            cum = 0
            for i, n in enumerate(sorted_nodes):
                fans = n.get("follower_count", 0)
                new_reach = fans if i == 0 else int(fans * (1 - SAME_PLATFORM_OVERLAP) ** i)
                cum += new_reach
            total_fwd = sum(n.get("forward_count", 0) for n in plat_nodes)
            fwd_reach = int(total_fwd * AVG_FORWARD_EXPOSURE)
            plat_total = cum + fwd_reach
            reach_by_platform[plat] = {
                "unique_fan_reach": cum,
                "forward_exposure": fwd_reach,
                "platform_total": plat_total,
            }
            total_unique += plat_total

        naive_total = sum(
            n.get("follower_count", 0) + n.get("forward_count", 0) * 100
            for n in nodes
        )

        return {
            "estimated_unique_reach": total_unique,
            "reach_by_platform": reach_by_platform,
            "breakdown": {
                "naive_sum": naive_total,
                "dedup_ratio": round(total_unique / max(1, naive_total), 2),
                "method": "平台内指数衰减去重 + 跨平台独立加和",
            },
        }

    def _build_timeline(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sorted_nodes = sorted(nodes, key=lambda n: n["post_time"])
        timeline = []
        for n in sorted_nodes:
            timeline.append({
                "time": n["post_time"].strftime("%Y-%m-%d %H:%M"),
                "account": n["account_name"],
                "source": n.get("source", ""),
                "action": "首次曝光" if n.get("parent_node_id") is None else f"转发自{n.get('parent_node_id')}",
                "follower_count": n.get("follower_count", 0),
            })
        return timeline

    def _build_graph_for_viz(self, G: nx.DiGraph, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """输出适配 ECharts/D3.js 力导向图的数据"""
        graph_nodes = []
        graph_links = []

        # 先算 pagerank 用于节点大小
        pr = nx.pagerank(G, weight="forward_count") if G.number_of_nodes() > 0 else {}

        for n in nodes:
            nid = n["node_id"]
            pr_val = pr.get(nid, 0.1)
            symbol_size = max(10, min(80, 15 + int(pr_val * 100)))

            if G.has_node(nid):
                category = self._node_category_graph(G, nid, n)
            else:
                category = 0

            graph_nodes.append({
                "id": nid,
                "name": n["account_name"],
                "symbolSize": symbol_size,
                "category": category,
                "follower_count": n.get("follower_count", 0),
                "source": n.get("source", ""),
                "pagerank": round(pr_val, 4),
            })

        for u, v in G.edges():
            graph_links.append({"source": u, "target": v})

        categories = [
            {"name": "普通用户"},
            {"name": "大V/意见领袖"},
            {"name": "官方媒体"},
            {"name": "初始爆料源"},
            {"name": "桥接节点"},
        ]

        return {
            "nodes": graph_nodes,
            "links": graph_links,
            "categories": categories,
        }

    def _node_category_graph(self, G: nx.DiGraph, nid: str, n: dict[str, Any]) -> int:
        """节点分类（0-4）"""
        if G.in_degree(nid) == 0:
            return 3
        if self._is_official_account(n["account_name"]):
            return 2
        if n.get("follower_count", 0) >= self.influencer_threshold:
            return 1
        return 0


# ====== 自测 ======
if __name__ == "__main__":
    from time_series.utils.mock_data import generate_mock_propagation_data

    print("=" * 60)
    print("传播溯源 v2.0 — networkx DiGraph + PageRank")
    print("=" * 60)

    nodes = generate_mock_propagation_data()
    tracer = PropagationTracer()
    result = tracer.analyze(nodes)

    # 源头
    srcs = result["source_nodes"]
    print(f"\n源头节点 ({len(srcs)}个):")
    for s in srcs:
        print(f"  [{s['node_id']}] {s['account_name']} ({s['platform']}) — {s['post_time']}")

    # 图统计
    gs = result["propagation_graph"]
    print(f"\n图统计:")
    print(f"  节点: {gs['node_count']}, 边: {gs['edge_count']}")
    print(f"  DAG: {gs['is_dag']}, 密度: {gs['density']}")
    print(f"  平均入度: {gs['avg_in_degree']}, 平均出度: {gs['avg_out_degree']}")
    print(f"  源头数: {gs['source_count']}, 叶子数: {gs['sink_count']}")
    print(f"  最长传播链: {result['propagation_depth']} 层")

    # 关键节点（图算法版）
    print(f"\n关键节点 (PageRank+介数+出度):")
    for kn in result["key_nodes"]:
        gs2 = kn["graph_scores"]
        print(f"  [{kn['role']}] {kn['account_name']}")
        print(f"    PageRank={gs2['pagerank']:.3f} 介数={gs2['betweenness']:.3f} "
              f"出度分={gs2['out_degree_score']:.3f} 综合={gs2['composite']:.3f}")

    # 触达
    reach = result["total_reach"]
    print(f"\n触达: {reach['estimated_unique_reach']:,} (旧: {reach['breakdown']['naive_sum']:,}, 去重比: {reach['breakdown']['dedup_ratio']})")

    # 可视化数据预览
    gv = result["graph_for_visualization"]
    print(f"\n可视化: {len(gv['nodes'])}节点, {len(gv['links'])}条边")
    print(f"  分类: {[c['name'] for c in gv['categories']]}")

    print(f"\n数据质量: {result['data_quality']}")

    # 新旧对比
    print(f"\n{'=' * 60}")
    print(f"新旧对比:")
    print(f"  旧: 嵌套dict树, 关键节点看粉丝数")
    print(f"  新: networkx DiGraph, PageRank+介数+出度三维综合")
