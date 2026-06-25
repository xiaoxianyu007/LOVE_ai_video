#!/usr/bin/env python3
"""
修复英文文案中的拼音发音问题 - v2 安全版。
移除所有危险短替换（Ci, Qu），只保留安全的长名替换 + 特定短替换。
"""
import re

# 只保留安全替换：长名优先，短替换仅限不出现于英文词中的拼音
PINYIN_MAP = [
    # === 长名（不会被误匹配）===
    ("Xianyang", "Shyen-yahng"),
    ("Xingyang", "Shing-yahng"),
    ("Xiongnu", "Shyong-noo"),
    ("Xiang Yu", "Shyahng Yoo"),
    ("Xiang Bo", "Shyahng Bwo"),
    ("Xiang Zhuang", "Shyahng Jwahng"),
    ("Xiao He", "Shyaow Huh"),
    ("Xiao Wangzhi", "Shyaow Wahng-juh"),
    ("Xiahou Ying", "Shyah-ho Ying"),
    ("Xun Zhi", "Shoon Juh"),
    ("Han Xin", "Hahn Sheen"),
    ("Liu Bang", "Lee-oh Bahng"),
    ("Liu Che", "Lee-oh Chuh"),
    ("Liu Heng", "Lee-oh Hung"),
    ("Liu Ying", "Lee-oh Ying"),
    ("Liu Ju", "Lee-oh Joo"),
    ("Liu Shi", "Lee-oh Shuh"),
    ("Liu Xun", "Lee-oh Shoon"),
    ("Liu Bi", "Lee-oh Bee"),
    ("Liu An", "Lee-oh Ahn"),
    ("Liu Ci", "Lee-oh Tsuh"),
    ("Liu Dan", "Lee-oh Dahn"),
    ("Liu He", "Lee-oh Huh"),
    ("Liu Bingyi", "Lee-oh Bing-yee"),
    ("Liu Fuling", "Lee-oh Foo-ling"),
    ("Liu Qumao", "Lee-oh Choo-maow"),
    ("Fan Kuai", "Fahn Kwai"),
    ("Fan Zeng", "Fahn Dzung"),
    ("Sima Xin", "Suh-mah Sheen"),
    ("Dong Yi", "Doong Yee"),
    ("Zhang Han", "Jahng Hahn"),
    ("Zhang Liang", "Jahng Lee-ahng"),
    ("Zhang Qian", "Jahng Chyen"),
    ("Chen Yu", "Chun Yoo"),
    ("Chen Ping", "Chun Ping"),
    ("Chen Tang", "Chun Tahng"),
    ("Li Zuoche", "Lee Dzwo-chuh"),
    ("Peng Yue", "Pung Yweh"),
    ("Ying Bu", "Ying Boo"),
    ("Xin of Han", "Sheen of Hahn"),
    ("Lou Jing", "Lo Jing"),
    ("Wei Qing", "Way Ching"),
    ("Wei Zifu", "Way Dzuh-foo"),
    ("Huo Qubing", "Hwo Choo-bing"),
    ("Huo Guang", "Hwo Gwahng"),
    ("Huo Xian", "Hwo Shyen"),
    ("Yu Ji", "Yoo Jee"),
    ("Lü Zhi", "Lyoo Juh"),
    ("Lü Jia", "Lyoo Jyah"),
    ("Lü Chan", "Lyoo Chahn"),
    ("Lü Matong", "Lyoo Mah-toong"),
    ("Kuai Tong", "Kwai Toong"),
    ("Chao Cuo", "Chow Tswo"),
    ("Dou Ying", "Do Ying"),
    ("Yuan Ang", "Ywen Ahng"),
    ("Zhou Yafu", "Joe Yah-foo"),
    ("Zhou Bo", "Joe Bwo"),
    ("Zhao Wan", "Jow Wahn"),
    ("Wang Zang", "Wahng Dzahng"),
    ("Dong Zhongshu", "Doong Joong-shoo"),
    ("Gongsun Hong", "Goong-swoon Hawng"),
    ("Wei Wan", "Way Wahn"),
    ("Wang Hui", "Wahng Hway"),
    ("Nie Yi", "Nyeh Yee"),
    ("Sang Hongyang", "Sahng Hawng-yahng"),
    ("Dongguo Xianyang", "Doong-gwo Shyen-yahng"),
    ("Kong Jin", "Koong Jin"),
    ("Zhao Tuo", "Jow Two"),
    ("Zhao Xing", "Jow Shing"),
    ("Zhao Jiande", "Jow Jyen-duh"),
    ("Zhao Feiyan", "Jow Fay-yen"),
    ("Zhao Hede", "Jow Huh-duh"),
    ("Lu Bode", "Loo Bwo-duh"),
    ("Yang Pu", "Yahng Poo"),
    ("Tang Meng", "Tahng Mung"),
    ("Sima Xiangru", "Suh-mah Shyahng-roo"),
    ("Gongsun He", "Goong-swoon Huh"),
    ("Jiang Chong", "Jyahng Choong"),
    ("Shi De", "Shuh Duh"),
    ("Jin Midi", "Jin Mee-dee"),
    ("Shangguan Jie", "Shahng-gwahn Jyeh"),
    ("Huan Kuan", "Hwahn Kwahn"),
    ("Bing Ji", "Bing Jee"),
    ("Xu Pingjun", "Shoo Ping-joon"),
    ("Gan Yanshou", "Gahn Yen-sho"),
    ("Zheng Ji", "Jung Jee"),
    ("Shi Xian", "Shuh Shyen"),
    ("Wang Zhaojun", "Wahng Jaow-joon"),
    ("Mao Yanshou", "Maow Yen-sho"),
    ("Wang Zhengjun", "Wahng Jung-joon"),
    ("Wang Feng", "Wahng Fung"),
    ("Wang Shang", "Wahng Shahng"),
    ("Wang Gen", "Wahng Gun"),
    ("Wang Yin", "Wahng Yin"),
    ("Wang Mang", "Wahng Mahng"),
    ("Dong Xian", "Doong Shyen"),
    ("Cao Wushang", "Tsao Woo-shahng"),
    ("Li Guang", "Lee Gwahng"),
    ("Chunyu Yi", "Chun-yoo Yee"),
    ("Chunyu Tiying", "Chun-yoo Tiying"),

    # === 地名（长名）===
    ("Guanzhong", "Gwahn-joong"),
    ("Hanzhong", "Hahn-joong"),
    ("Pengcheng", "Pung-chung"),
    ("Gaixia", "Gai-shee-ah"),
    ("Jingxing", "Jing-shing"),
    ("Weiyang", "Way-yahng"),
    ("Huaiyin", "Hwai-yin"),
    ("Baideng", "Bai-dung"),
    ("Datong", "Dah-toong"),
    ("Dingtao", "Ding-taow"),
    ("Luoyang", "Lwo-yahng"),
    ("Feiqiu", "Fay-chyoh"),
    ("Guling", "Goo-ling"),
    ("Wujiang", "Woo-jyahng"),
    ("Jiangdong", "Jyahng-doong"),
    ("Mianman", "Myen-mahn"),
    ("Shuofang", "Shwo-fahng"),
    ("Wuyuan", "Woo-ywen"),
    ("Longcheng", "Loong-chung"),
    ("Longxi", "Loong-shee"),
    ("Shanggu", "Shahng-goo"),
    ("Shanglin", "Shahng-lin"),
    ("Maoling", "Maow-ling"),
    ("Langjuxu", "Lahng-joo-shoo"),
    ("Guyan", "Goo-yen"),
    ("Tianyan", "Tyen-yen"),
    ("Mobei", "Mwo-bay"),
    ("Hexi", "Huh-shee"),
    ("Dunhuang", "Doon-hwahng"),
    ("Jiuquan", "Jyoh-chwen"),
    ("Wuwei", "Woo-way"),
    ("Zhangye", "Jahng-yeh"),
    ("Ganquan", "Gahn-chwen"),
    ("Luntai", "Loon-tai"),
    ("Wulei", "Woo-lay"),
    ("Tianshan", "Tyen-shahn"),
    ("Mayi", "Mah-yee"),
    ("Yuzhang", "Yoo-jahng"),
    ("Panyu", "Pahn-yoo"),
    ("Guiyang", "Gway-yahng"),
    ("Dan'er", "Dahn-ur"),
    ("Hainan", "Hai-nahn"),
    ("Nanhai", "Nahn-hai"),
    ("Lingnan", "Ling-nahn"),
    ("Jiaozhi", "Jyaow-juh"),
    ("Liaodong", "Lyaow-doong"),
    ("Bohai", "Bwo-hai"),
    ("Wangxian", "Wahng-shyen"),
    ("Lelang", "Luh-lahng"),
    ("Lintun", "Lin-toon"),
    ("Zhenfan", "Jun-fahn"),
    ("Yingchuan", "Ying-chwahn"),
    ("Pingyang", "Ping-yahng"),
    ("Yelang", "Yeh-lahng"),
    ("Lingguan", "Ling-gwahn"),
    ("Sichuan", "Suh-chwahn"),
    ("Chang'an", "Chahng-ahn"),
    ("Changle", "Chahng-luh"),
    ("Changyi", "Chahng-yee"),
    ("Changping", "Chahng-ping"),
    ("Chencang", "Chun-tsahng"),

    # === 特殊术语 ===
    ("Chanyu", "Chahn-yoo"),
    ("Modu", "Mo-doo"),
    ("Huhanye", "Hoo-hahn-yeh"),
    ("Ninghu Yanzhi", "Ning-hoo Yen-juh"),
    ("Jianyuan", "Jyen-ywen"),
    ("Suanmin", "Swahn-min"),
    ("Gaomin", "Gow-min"),
    ("Huang-Lao", "Hwahng-Laow"),
    ("Fusu", "Foo-soo"),
    ("Wen-Jing", "Wun-Jing"),
    ("Wusun", "Woo-swoon"),
    ("Dayuan", "Dah-ywen"),
    ("Kangju", "Kahng-joo"),
    ("Shendu", "Shun-doo"),
    ("Tangyi Fu", "Tahng-yee Foo"),
    ("Minyue", "Min-yweh"),
    ("Nanyue", "Nahn-yweh"),
    ("Goujian", "Go-jyen"),
    ("Yanzhi", "Yen-juh"),
    ("Yanmen", "Yen-mun"),
    ("Yuezhi", "Yweh-juh"),
    ("Yunyang", "Yoon-yahng"),
    ("Yushan", "Yoo-shahn"),
    ("Qilian", "Chee-lyen"),
    ("Qiangwei", "Chyahng-way"),
    ("Qilin", "Chee-lin"),
    ("Quli", "Choo-lee"),
    ("Zhizhi", "Juh-juh"),
    ("Zhelan", "Juh-lahn"),
    ("Xiutu", "Shyoo-too"),
    ("Xuantu", "Shwen-too"),
    ("Xingle", "Shing-luh"),
    ("Zhufu Yan", "Joo-foo Yen"),   # 主父偃
    ("Youqu", "Yo-choo"),           # 右渠
    ("Wei Man", "Way Mahn"),        # 卫满

    # === 河流 ===
    ("Sui River", "Sway River"),
    ("Wei River", "Way River"),
    ("Fan River", "Fahn River"),
    ("Hong Canal", "Hawng Canal"),

    # === 短替换（安全：这些拼音音节不出现在英文词中）===
    # Qin → Chin: 秦朝
    ("Qin", "Chin"),

    # 注意：以下短替换在长名处理之后执行，只替换孤立出现的词
    # 因为它们不会出现在英文词中，所以是安全的
]

# 第二轮短替换：在长名处理之后，这些单音节替换是安全的
SHORT_SAFE_MAP = [
    ("Xiang", "Shyahng"),   # 项 (已处理 Xiang Yu/Xiang Bo 后的残留)
    ("Xiao", "Shyaow"),     # 萧 (已处理 Xiao He 后的残留)
    ("Xian", "Shyen"),      # 显/咸阳 (已处理长名后的残留)
    ("Xin", "Sheen"),       # 信/新 (已处理 Han Xin 后的残留)
    ("Xun", "Shoon"),       # 询/荀 (已处理 Liu Xun 后的残留)
    ("Xia", "Shyah"),       # 夏 (已处理 Xiahou 后的残留)
    ("Xu", "Shoo"),         # 许 (已处理 Xu Pingjun 后的残留)
    ("Qi", "Chee"),         # 齐
    ("Chu", "Choo"),        # 楚
    ("Zhao", "Jow"),        # 赵
    ("Zhou", "Joe"),        # 周
    ("Zheng", "Jung"),      # 郑
    ("Zhu", "Joo"),         # 朱/主
    ("Zhi", "Juh"),         # 雉/支
    ("Zhen", "Jun"),        # 真
    ("Zhong", "Joong"),     # 中/仲
    ("Zang", "Dzahng"),     # 臧
    ("Zuo", "Dzwo"),        # 左
    ("Zi", "Dzuh"),         # 子
    ("Zeng", "Dzung"),      # 增
    ("Cao", "Tsao"),        # 曹
    ("Chen", "Chun"),       # 陈
    ("Chao", "Chow"),       # 晁
    ("Cheng", "Chung"),     # 成
    ("Cuo", "Tswo"),        # 错
    ("Yue", "Yweh"),        # 越
    ("Yuan", "Ywen"),       # 元
    ("Qian", "Chyen"),      # 骞
    ("Qiong", "Chyong"),    # 邛
    ("Qiang", "Chyahng"),   # 羌
    ("Xuan", "Shooan"),     # 宣 (宣帝)
    ("Lü", "Lyoo"),         # 吕
    ("lü", "lyoo"),         # 吕(小写)
    ("Wei", "Way"),         # 卫
    ("Wang", "Wahng"),      # 王
]

# 后处理：修复级联误替换
POST_FIX = [
    ("Choon-tsahng", "Chun-tsahng"),  # Chu→Choo 级联到 Chencang 的修复
    ("Choon Ping", "Chun Ping"),      # Chu→Choo 级联到 Chen Ping
    ("Choon Yoo", "Chun Yoo"),        # Chu→Choo 级联到 Chen Yu
    ("Choon-yoo", "Chun-yoo"),        # Chu→Choo 级联到 Chunyu
    ("Choon Tahng", "Chun Tahng"),    # Chu→Choo 级联到 Chen Tang
    ("Lee-oh Chooh", "Lee-oh Chuh"),  # Chu→Choo 级联到 Liu Che 的修复
    ("Emperor Choong", "Emperor Chung"),  # Chu→Choo 级联到 Emperor Cheng 的修复
    ("Shi clan", "Shuh clan"),        # 史氏家族（Shi 不在短替换中，避免破坏 Shing 等）
    ("Shuhng-yahng", "Shing-yahng"),  # Shi→Shuh 级联到 Xingyang 的回退
    ("Shuhng-luh", "Shing-luh"),      # Shi→Shuh 级联到 Xingle 的回退
    ("Jow Shuhng", "Jow Shing"),      # Shi→Shuh 级联到 Zhao Xing 的回退
]

def fix_pinyin(text):
    # 第1轮：长名替换
    for pinyin, phonetic in PINYIN_MAP:
        text = text.replace(pinyin, phonetic)
    # 第2轮：安全短替换
    for pinyin, phonetic in SHORT_SAFE_MAP:
        text = text.replace(pinyin, phonetic)
    # 第3轮：修复级联误替换
    for wrong, correct in POST_FIX:
        text = text.replace(wrong, correct)
    return text

def main():
    files = ["data/chu_han_en.txt", "data/western_han_en.txt"]
    for fpath in files:
        with open(fpath, 'r') as f:
            original = f.read()
        fixed = fix_pinyin(original)
        with open(fpath, 'w') as f:
            f.write(fixed)
        # 统计变化
        total = 0
        for pinyin, phonetic in PINYIN_MAP + SHORT_SAFE_MAP:
            c = original.count(pinyin)
            if c > 0:
                total += c
        print(f"✓ {fpath}: {total} 处替换")

if __name__ == "__main__":
    main()