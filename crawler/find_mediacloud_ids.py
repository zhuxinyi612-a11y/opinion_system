import os
from dotenv import load_dotenv
import mediacloud.api


def show_items(title, items, id_key="id", max_show=20):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

    if not items:
        print("没有结果")
        return

    for item in items[:max_show]:
        print({
            "id": item.get(id_key),
            "name": item.get("name") or item.get("label"),
            "label": item.get("label"),
            "url": item.get("url") or item.get("homepage"),
            "domain": item.get("domain"),
            "pub_country": item.get("pub_country"),
            "language": item.get("primary_language"),
        })


def main():
    load_dotenv()

    token = os.getenv("MEDIACLOUD_API_KEY", "").strip()
    if not token:
        print("[ERROR] 没有找到 MEDIACLOUD_API_KEY")
        return

    directory = mediacloud.api.DirectoryApi(token)

    # 1. 先找可能的中文/中国 collections
    collection_keywords = [
        "China",
        "Chinese",
        "Hong Kong",
        "Taiwan",
        "Asia",
    ]

    for kw in collection_keywords:
        try:
            res = directory.collection_list(
                platform="online_news",
                name=kw,
                limit=20,
                offset=0,
            )
            show_items(f"Collections 搜索：{kw}", res.get("results", []))
        except Exception as e:
            print(f"[WARN] collection 搜索失败：{kw} -> {e}")

    # 2. 再找具体中文媒体 source
    source_keywords = [
    # =========================
    # 央媒 / 全国综合新闻
    # =========================
    "people.com.cn",
    "xinhuanet.com",
    "news.cn",
    "cctv.com",
    "news.cctv.com",
    "cntv.cn",
    "chinanews.com.cn",
    "china.com.cn",
    "cri.cn",
    "cnr.cn",
    "ce.cn",
    "gmw.cn",
    "youth.cn",
    "huanqiu.com",
    "legaldaily.com.cn",
    "rmfyb.chinacourt.org",
    "jcrb.com",
    "workercn.cn",
    "farmer.com.cn",
    "stdaily.com",
    "cssn.cn",
    "cppcc.gov.cn",

    # =========================
    # 市场化 / 综合新闻媒体
    # =========================
    "thepaper.cn",
    "caixin.com",
    "jiemian.com",
    "yicai.com",
    "21jingji.com",
    "stcn.com",
    "eeo.com.cn",
    "nbd.com.cn",
    "time-weekly.com",
    "chinatimes.net.cn",
    "infzm.com",
    "guancha.cn",
    "huxiu.com",
    "36kr.com",
    "tmtpost.com",
    "ithome.com",
    "cnblogs.com",
    "donews.com",
    "techweb.com.cn",
    "cnbeta.com.tw",
    "sootoo.com",
    "iyiou.com",
    "lieyunwang.com",

    # =========================
    # 门户新闻
    # =========================
    "sina.com.cn",
    "news.sina.com.cn",
    "finance.sina.com.cn",
    "ent.sina.com.cn",
    "sports.sina.com.cn",
    "tech.sina.com.cn",
    "qq.com",
    "news.qq.com",
    "finance.qq.com",
    "new.qq.com",
    "163.com",
    "news.163.com",
    "money.163.com",
    "ent.163.com",
    "sports.163.com",
    "sohu.com",
    "news.sohu.com",
    "business.sohu.com",
    "sports.sohu.com",
    "ifeng.com",
    "news.ifeng.com",
    "finance.ifeng.com",
    "ent.ifeng.com",

    # =========================
    # 今日头条 / 字节系 / 短视频相关
    # MediaCloud 不一定收录平台内容，但可以找相关报道源
    # =========================
    "toutiao.com",
    "jinritemai.com",
    "douyin.com",
    "iesdouyin.com",
    "ixigua.com",
    "volcengine.com",
    "bytedance.com",
    "kuaishou.com",
    "gifshow.com",
    "bilibili.com",
    "acfun.cn",
    "youku.com",
    "iqiyi.com",
    "mgtv.com",
    "tencentvideo.com",

    # =========================
    # 社交平台 / 社区 / 内容平台
    # =========================
    "weibo.com",
    "s.weibo.com",
    "zhihu.com",
    "xiaohongshu.com",
    "douban.com",
    "tieba.baidu.com",
    "baijiahao.baidu.com",
    "mp.weixin.qq.com",
    "wx.qq.com",

    # =========================
    # 教育 / 校园 / 高校 / 考试
    # =========================
    "moe.gov.cn",
    "jyb.cn",
    "eol.cn",
    "gaokao.eol.cn",
    "kaoyan.eol.cn",
    "chsi.com.cn",
    "neea.edu.cn",
    "jsj.edu.cn",
    "eduyun.cn",
    "smartedu.cn",
    "univs.cn",
    "cssn.cn",
    "k618.cn",
    "school.edu.cn",
    "cernet.com",
    "cernet.edu.cn",

    # =========================
    # 医疗 / 健康 / 公共卫生
    # =========================
    "nhc.gov.cn",
    "chinacdc.cn",
    "cdc.gov.cn",
    "nmpa.gov.cn",
    "samr.gov.cn",
    "health.people.com.cn",
    "health.china.com.cn",
    "health.cnr.cn",
    "medlive.cn",
    "dxy.cn",
    "chunyuyisheng.com",
    "haodf.com",
    "yixue.com",
    "yaozh.com",
    "pharmnet.com.cn",
    "cn-healthcare.com",
    "vcbeat.top",

    # =========================
    # 食品安全 / 消费 / 购物 / 电商
    # =========================
    "samr.gov.cn",
    "cca.org.cn",
    "315online.com",
    "ccn.com.cn",
    "foodmate.net",
    "foodsafetynews.com.cn",
    "cnfood.cn",
    "cfnews.com.cn",
    "taobao.com",
    "tmall.com",
    "jd.com",
    "pinduoduo.com",
    "suning.com",
    "vip.com",
    "meituan.com",
    "dianping.com",
    "ele.me",
    "alibaba.com",
    "alizila.com",

    # =========================
    # 民生 / 社会 / 法治 / 公共安全
    # =========================
    "mps.gov.cn",
    "mem.gov.cn",
    "mca.gov.cn",
    "mohrss.gov.cn",
    "acftu.org",
    "chinacourt.org",
    "court.gov.cn",
    "spp.gov.cn",
    "legaldaily.com.cn",
    "cctv.com",
    "news.cctv.com",
    "society.people.com.cn",
    "society.china.com.cn",

    # =========================
    # 财经 / 市场经济 / 金融 / 股市
    # =========================
    "mof.gov.cn",
    "pbc.gov.cn",
    "csrc.gov.cn",
    "cbirc.gov.cn",
    "stats.gov.cn",
    "ndrc.gov.cn",
    "mofcom.gov.cn",
    "sse.com.cn",
    "szse.cn",
    "neeq.com.cn",
    "cnstock.com",
    "cs.com.cn",
    "jrj.com.cn",
    "eastmoney.com",
    "hexun.com",
    "10jqka.com.cn",
    "wallstreetcn.com",
    "cls.cn",
    "gelonghui.com",
    "xueqiu.com",

    # =========================
    # 房产 / 城市 / 物业 / 租房
    # =========================
    "mohurd.gov.cn",
    "fang.com",
    "anjuke.com",
    "lianjia.com",
    "ke.com",
    "58.com",
    "ganji.com",
    "house.people.com.cn",
    "house.ifeng.com",
    "house.sina.com.cn",
    "focus.cn",
    "leju.com",

    # =========================
    # 汽车 / 新能源车 / 交通
    # =========================
    "mot.gov.cn",
    "miit.gov.cn",
    "autohome.com.cn",
    "pcauto.com.cn",
    "xcar.com.cn",
    "cheshi.com",
    "dongchedi.com",
    "yiche.com",
    "bitauto.com",
    "d1ev.com",
    "gasgoo.com",
    "nev.ofweek.com",
    "cnev.cn",

    # =========================
    # 科技 / 互联网 / AI / 数码
    # =========================
    "miit.gov.cn",
    "cac.gov.cn",
    "most.gov.cn",
    "36kr.com",
    "huxiu.com",
    "tmtpost.com",
    "ithome.com",
    "cnbeta.com.tw",
    "techweb.com.cn",
    "pingwest.com",
    "geekpark.net",
    "ifanr.com",
    "leiphone.com",
    "jiqizhixin.com",
    "ofweek.com",
    "elecfans.com",
    "eet-china.com",
    "semimedia.cc",

    # =========================
    # 娱乐 / 明星 / 饭圈 / 影视
    # =========================
    "ent.sina.com.cn",
    "ent.qq.com",
    "ent.163.com",
    "ent.ifeng.com",
    "1905.com",
    "mtime.com",
    "maoyan.com",
    "douban.com",
    "piaofang.maoyan.com",
    "yule.sohu.com",
    "kankanews.com",
    "mgtv.com",
    "iqiyi.com",
    "youku.com",
    "tencentvideo.com",

    # =========================
    # 电影 / 电视剧 / 综艺 / 文娱产业
    # =========================
    "1905.com",
    "mtime.com",
    "maoyan.com",
    "piaofang.maoyan.com",
    "douban.com",
    "entgroup.cn",
    "csmpte.com",
    "filmart.cn",
    "chinafilm.gov.cn",
    "nrta.gov.cn",

    # =========================
    # 体育 / 世界杯 / 足球 / 篮球
    # =========================
    "sports.sina.com.cn",
    "sports.qq.com",
    "sports.163.com",
    "sports.sohu.com",
    "sports.cctv.com",
    "zhibo8.cc",
    "hupu.com",
    "dongqiudi.com",
    "ppsport.com",
    "fifa.com",
    "the-afc.com",
    "nba.com",
    "cba.net.cn",
    "olympics.com",
    "sports.people.com.cn",

    # =========================
    # 传统文化 / 文旅 / 博物馆 / 非遗
    # =========================
    "mct.gov.cn",
    "chnmuseum.cn",
    "ihchina.cn",
    "ccnt.com.cn",
    "wenming.cn",
    "cctv.com",
    "culture.people.com.cn",
    "culture.china.com.cn",
    "art.people.com.cn",
    "artron.net",
    "dpm.org.cn",
    "nmch.gov.cn",

    # =========================
    # 旅游 / 酒店 / 出行
    # =========================
    "mct.gov.cn",
    "ctrip.com",
    "trip.com",
    "qunar.com",
    "mafengwo.cn",
    "tuniu.com",
    "ly.com",
    "fliggy.com",
    "travel.people.com.cn",
    "travel.china.com.cn",

    # =========================
    # 灾害 / 天气 / 应急 / 环境
    # =========================
    "mem.gov.cn",
    "cma.gov.cn",
    "weather.com.cn",
    "mee.gov.cn",
    "mwr.gov.cn",
    "cea.gov.cn",
    "eq-cedpc.cn",
    "forestry.gov.cn",
    "greenpeace.org.cn",
    "chinawater.com.cn",
    "huanbao.bjx.com.cn",

    # =========================
    # 游戏 / 电竞 / 二次元
    # =========================
    "gamersky.com",
    "3dmgame.com",
    "ali213.net",
    "17173.com",
    "duowan.com",
    "youxiputao.com",
    "game.china.com",
    "game.people.com.cn",
    "game.qq.com",
    "esports.qq.com",
    "bilibili.com",
    "acg.178.com",

    # =========================
    # 地方媒体：北京 / 上海 / 广东 / 江苏 / 浙江 / 山东等
    # =========================
    "bjnews.com.cn",
    "ynet.com",
    "takefoto.cn",
    "beijing.gov.cn",
    "eastday.com",
    "shobserver.com",
    "thepaper.cn",
    "jfdaily.com",
    "southcn.com",
    "oeeee.com",
    "dayoo.com",
    "gd.gov.cn",
    "jschina.com.cn",
    "xdkb.net",
    "yangtse.com",
    "zjol.com.cn",
    "hznews.com",
    "dzwww.com",
    "qlwb.com.cn",
    "dahe.cn",
    "henan.gov.cn",
    "cnhubei.com",
    "hbnews.net",
    "rednet.cn",
    "voc.com.cn",
    "scdaily.cn",
    "scol.com.cn",
    "newssc.org",
    "cqnews.net",
    "yninfo.com",
    "yunnan.cn",
    "gxnews.com.cn",
    "hinews.cn",
    "fjsen.com",
    "taihainet.com",
    "hebei.com.cn",
    "hebnews.cn",
    "lnnews.com.cn",
    "nmgnews.com.cn",
    "sxrb.com",
    "sxgov.cn",
    "gansudaily.com.cn",
    "nxnews.net",
    "ts.cn",
    "xjbs.com.cn",
    "tibet.cn",
        # =========================
    # 音乐 / 演唱会 / 音综 / 音乐平台
    # =========================
    "music.163.com",
    "y.qq.com",
    "kugou.com",
    "kuwo.cn",
    "xiami.com",
    "migu.cn",
    "5sing.kugou.com",
    "douban.com",
    "billboardchina.cn",
    "midifan.com",
    "musiceol.com",
    "cnki.net",
    "ent.sina.com.cn",
    "ent.qq.com",
    "ent.163.com",
    "ent.ifeng.com",
    "yule.sohu.com",
    "1905.com",
    "damai.cn",
    "maoyan.com",
    "piaofang.maoyan.com",

    # =========================
    # 人才招聘 / 就业 / 劳动关系 / 职场舆情
    # =========================
    "mohrss.gov.cn",
    "acftu.org",
    "workercn.cn",
    "chinajob.com",
    "job.mohrss.gov.cn",
    "zhaopin.com",
    "51job.com",
    "liepin.com",
    "bosszhipin.com",
    "kanzhun.com",
    "lagou.com",
    "maimai.cn",
    "yingjiesheng.com",
    "shixiseng.com",
    "newjobs.com.cn",
    "chinahr.com",
    "cjol.com",
    "hr.com.cn",
    "cyol.com",
    "jyb.cn",
    "eol.cn",

    # =========================
    # 健康 / 医疗 / 医药 / 医美 / 养老
    # =========================
    "nhc.gov.cn",
    "nmpa.gov.cn",
    "chinacdc.cn",
    "cdc.gov.cn",
    "samr.gov.cn",
    "health.people.com.cn",
    "health.china.com.cn",
    "health.cnr.cn",
    "jiankang.163.com",
    "health.sina.com.cn",
    "health.qq.com",
    "medlive.cn",
    "dxy.cn",
    "haodf.com",
    "chunyuyisheng.com",
    "yixue.com",
    "yaozh.com",
    "pharmnet.com.cn",
    "cn-healthcare.com",
    "vcbeat.top",
    "bioon.com",
    "instrument.com.cn",
    "hc3i.cn",
    "a-hospital.com",
    "yanglao.com.cn",

    # =========================
    # 食品安全 / 餐饮 / 外卖 / 消费维权
    # =========================
    "samr.gov.cn",
    "cca.org.cn",
    "315online.com",
    "ccn.com.cn",
    "foodmate.net",
    "foodsafetynews.com.cn",
    "cnfood.cn",
    "cfnews.com.cn",
    "food.china.com.cn",
    "food.people.com.cn",
    "spzx.foods1.com",
    "meituan.com",
    "dianping.com",
    "ele.me",
    "jd.com",
    "taobao.com",
    "tmall.com",
    "pinduoduo.com",
    "suning.com",
    "vip.com",
    "blackcat.sina.com.cn",

    # =========================
    # 消防 / 应急管理 / 安全生产 / 灾害救援
    # =========================
    "mem.gov.cn",
    "119.gov.cn",
    "xfj.mem.gov.cn",
    "mps.gov.cn",
    "cma.gov.cn",
    "weather.com.cn",
    "mwr.gov.cn",
    "cea.gov.cn",
    "mee.gov.cn",
    "forestry.gov.cn",
    "chinawater.com.cn",
    "safety.com.cn",
    "aqsc.cn",
    "chinasafety.gov.cn",
    "fire.hc360.com",
    "fire.people.com.cn",
    "society.people.com.cn",
    "news.cctv.com",

    # =========================
    # 诈骗防范 / 反诈 / 网络安全 / 个人信息保护
    # =========================
    "mps.gov.cn",
    "12321.cn",
    "cac.gov.cn",
    "cert.org.cn",
    "isc.org.cn",
    "cnvd.org.cn",
    "cnnvd.org.cn",
    "beian.miit.gov.cn",
    "miit.gov.cn",
    "pbc.gov.cn",
    "cbirc.gov.cn",
    "csrc.gov.cn",
    "spp.gov.cn",
    "court.gov.cn",
    "chinacourt.org",
    "legaldaily.com.cn",
    "jcrb.com",
    "safe.china.com.cn",
    "cyberpolice.cn",
    "net.china.com.cn",
    "finance.people.com.cn",
    "blackcat.sina.com.cn",

    # =========================
    # 政府工作 / 政务公开 / 政策 / 监管
    # =========================
    "gov.cn",
    "www.gov.cn",
    "npc.gov.cn",
    "cppcc.gov.cn",
    "xinhuanet.com",
    "people.com.cn",
    "cctv.com",
    "news.cctv.com",
    "ndrc.gov.cn",
    "mof.gov.cn",
    "mofcom.gov.cn",
    "miit.gov.cn",
    "mot.gov.cn",
    "mohurd.gov.cn",
    "moe.gov.cn",
    "mca.gov.cn",
    "mohrss.gov.cn",
    "nhc.gov.cn",
    "samr.gov.cn",
    "nmpa.gov.cn",
    "cac.gov.cn",
    "mem.gov.cn",
    "mps.gov.cn",
    "mee.gov.cn",
    "pbc.gov.cn",
    "stats.gov.cn",
    "audit.gov.cn",
    "customs.gov.cn",
    "chinatax.gov.cn",
    "safe.gov.cn",
    "nrta.gov.cn",
    "mct.gov.cn",
    "most.gov.cn",
    "agri.cn",
    "forestry.gov.cn",

    # =========================
    # 生活服务 / 民生投诉 / 本地服务
    # =========================
    "12345.gov.cn",
    "people.com.cn",
    "society.people.com.cn",
    "blackcat.sina.com.cn",
    "tousu.sina.com.cn",
    "315online.com",
    "cca.org.cn",
    "58.com",
    "ganji.com",
    "anjuke.com",
    "lianjia.com",
    "ke.com",
    "meituan.com",
    "dianping.com",
    "ctrip.com",
    "qunar.com",
    "fliggy.com",
    "tuniu.com",
]

    all_source_ids = []

    for kw in source_keywords:
        try:
            res = directory.source_list(
                platform="online_news",
                name=kw,
                limit=10,
                offset=0,
            )
            items = res.get("results", [])
            show_items(f"Sources 搜索：{kw}", items)

            for item in items:
                sid = item.get("id")
                if sid and sid not in all_source_ids:
                    all_source_ids.append(sid)

        except Exception as e:
            print(f"[WARN] source 搜索失败：{kw} -> {e}")

    print("\n" + "=" * 60)
    print("建议复制到 .env 的 MEDIACLOUD_SOURCE_IDS：")
    print("=" * 60)

    if all_source_ids:
        print(",".join(str(x) for x in all_source_ids))
    else:
        print("没有找到 source_ids，可以换关键词继续搜")


if __name__ == "__main__":
    main()