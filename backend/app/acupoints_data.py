"""Os 361 pontos clássicos de acupuntura (nomenclatura padrão da OMS) e suas posições no mapa.

- Siglas da acupuntura CHINESA (LU, LI, ST, SP, HT, SI, BL, KI, PC, SJ, GB, LR, DU, REN), com o
  código internacional da OMS ao lado (TE, GV e CV no lugar de SJ, DU e REN).
  As tabelas abaixo ainda usam as siglas brasileiras antigas (P, IG, E…) como chave interna:
  a conversão para as siglas chinesas é feita por PT_TO_CN.
- Nomes em pinyin. Códigos, nomes e meridianos são dados técnicos padronizados (uso livre).
- POSIÇÕES ESQUEMÁTICAS: o mapa é um desenho, não um atlas anatômico. Cada meridiano tem alguns
  pontos de referência ("âncoras") e os demais são distribuídos entre eles ao longo do trajeto.
  A administradora pode arrastar qualquer ponto para corrigir a posição no painel.
- Localização e indicações começam em branco: devem ser escritas pela própria clínica.

Sistema de coordenadas: desenho de 300 x 710 (frente e costas). As coordenadas abaixo são do
lado esquerdo da tela; meridianos bilaterais são espelhados automaticamente (x -> 300 - x).
"""

MERIDIANS = [
    # código PT, código OMS, nome, cor, elemento, bilateral
    ("P", "LU", "Pulmão", "#5b8def", "Metal", True),
    ("IG", "LI", "Intestino Grosso", "#3f6fd1", "Metal", True),
    ("E", "ST", "Estômago", "#e0a82e", "Terra", True),
    ("BP", "SP", "Baço-Pâncreas", "#c98a12", "Terra", True),
    ("C", "HT", "Coração", "#e04a5f", "Fogo", True),
    ("ID", "SI", "Intestino Delgado", "#c2334a", "Fogo", True),
    ("B", "BL", "Bexiga", "#2b9bb0", "Água", True),
    ("R", "KI", "Rim", "#1f7487", "Água", True),
    ("PC", "PC", "Pericárdio", "#e46aa8", "Fogo", True),
    ("TA", "TE", "Triplo Aquecedor", "#b24d8a", "Fogo", True),
    ("VB", "GB", "Vesícula Biliar", "#3fae5a", "Madeira", True),
    ("F", "LR", "Fígado", "#2a8a43", "Madeira", True),
    ("VG", "GV", "Vaso Governador", "#7800b4", "—", False),
    ("VC", "CV", "Vaso Concepção", "#9b42c7", "—", False),
]

# Sigla antiga (escola francesa/brasileira) -> sigla chinesa usada no sistema
PT_TO_CN = {"P": "LU", "IG": "LI", "E": "ST", "BP": "SP", "C": "HT", "ID": "SI", "B": "BL", "R": "KI",
            "PC": "PC", "TA": "SJ", "VB": "GB", "F": "LR", "VG": "DU", "VC": "REN"}
CN_TO_PT = {cn: pt for pt, cn in PT_TO_CN.items()}


def to_cn(code):
    """'VB20' -> 'GB20'. Códigos que não são de meridiano (OR-..., EX-...) ficam iguais."""
    letters = code.rstrip("0123456789")
    number = code[len(letters):]
    return PT_TO_CN[letters] + number if number and letters in PT_TO_CN else code


NAMES = {
    "P": "Zhongfu Yunmen Tianfu Xiabai Chize Kongzui Lieque Jingqu Taiyuan Yuji Shaoshang",
    "IG": "Shangyang Erjian Sanjian Hegu Yangxi Pianli Wenliu Xialian Shanglian Shousanli Quchi Zhouliao "
          "Shouwuli Binao Jianyu Jugu Tianding Futu Kouheliao Yingxiang",
    "E": "Chengqi Sibai Juliao Dicang Daying Jiache Xiaguan Touwei Renying Shuitu Qishe Quepen Qihu Kufang "
         "Wuyi Yingchuang Ruzhong Rugen Burong Chengman Liangmen Guanmen Taiyi Huaroumen Tianshu Wailing "
         "Daju Shuidao Guilai Qichong Biguan Futu Yinshi Liangqiu Dubi Zusanli Shangjuxu Tiaokou Xiajuxu "
         "Fenglong Jiexi Chongyang Xiangu Neiting Lidui",
    "BP": "Yinbai Dadu Taibai Gongsun Shangqiu Sanyinjiao Lougu Diji Yinlingquan Xuehai Jimen Chongmen "
          "Fushe Fujie Daheng Fuai Shidou Tianxi Xiongxiang Zhourong Dabao",
    "C": "Jiquan Qingling Shaohai Lingdao Tongli Yinxi Shenmen Shaofu Shaochong",
    "ID": "Shaoze Qiangu Houxi Wangu Yanggu Yanglao Zhizheng Xiaohai Jianzhen Naoshu Tianzong Bingfeng "
          "Quyuan Jianwaishu Jianzhongshu Tianchuang Tianrong Quanliao Tinggong",
    "B": "Jingming Cuanzhu Meichong Qucha Wuchu Chengguang Tongtian Luoque Yuzhen Tianzhu Dazhu Fengmen "
         "Feishu Jueyinshu Xinshu Dushu Geshu Ganshu Danshu Pishu Weishu Sanjiaoshu Shenshu Qihaishu "
         "Dachangshu Guanyuanshu Xiaochangshu Pangguangshu Zhonglushu Baihuanshu Shangliao Ciliao "
         "Zhongliao Xialiao Huiyang Chengfu Yinmen Fuxi Weiyang Weizhong Fufen Pohu Gaohuang Shentang "
         "Yixi Geguan Hunmen Yanggang Yishe Weicang Huangmen Zhishi Baohuang Zhibian Heyang Chengjin "
         "Chengshan Feiyang Fuyang Kunlun Pucan Shenmai Jinmen Jinggu Shugu Zutonggu Zhiyin",
    "R": "Yongquan Rangu Taixi Dazhong Shuiquan Zhaohai Fuliu Jiaoxin Zhubin Yingu Henggu Dahe Qixue "
         "Siman Zhongzhu Huangshu Shangqu Shiguan Yindu Futonggu Youmen Bulang Shenfeng Lingxu Shencang "
         "Yuzhong Shufu",
    "PC": "Tianchi Tianquan Quze Ximen Jianshi Neiguan Daling Laogong Zhongchong",
    "TA": "Guanchong Yemen Zhongzhu Yangchi Waiguan Zhigou Huizong Sanyangluo Sidu Tianjing Qinglengyuan "
          "Xiaoluo Naohui Jianliao Tianliao Tianyou Yifeng Chimai Luxi Jiaosun Ermen Erheliao Sizhukong",
    "VB": "Tongziliao Tinghui Shangguan Hanyan Xuanlu Xuanli Qubin Shuaigu Tianchong Fubai Touqiaoyin "
          "Wangu Benshen Yangbai Toulinqi Muchuang Zhengying Chengling Naokong Fengchi Jianjing Yuanye "
          "Zhejin Riyue Jingmen Daimai Wushu Weidao Juliao Huantiao Fengshi Zhongdu Xiyangguan "
          "Yanglingquan Yangjiao Waiqiu Guangming Yangfu Xuanzhong Qiuxu Zulinqi Diwuhui Xiaxi Zuqiaoyin",
    "F": "Dadun Xingjian Taichong Zhongfeng Ligou Zhongdu Xiguan Ququan Yinbao Zuwuli Yinlian Jimai "
         "Zhangmen Qimen",
    "VG": "Changqiang Yaoshu Yaoyangguan Mingmen Xuanshu Jizhong Zhongshu Jinsuo Zhiyang Lingtai Shendao "
          "Shenzhu Taodao Dazhui Yamen Fengfu Naohu Qiangjian Houding Baihui Qianding Xinhui Shangxing "
          "Shenting Suliao Shuigou Duiduan Yinjiao",
    "VC": "Huiyin Qugu Zhongji Guanyuan Shimen Qihai Yinjiao Shenque Shuifen Xiawan Jianli Zhongwan "
          "Shangwan Juque Jiuwei Zhongting Danzhong Yutang Zigong Huagai Xuanji Tiantu Lianquan Chengjiang",
}

F, K = "front", "back"
# Âncoras: (número do ponto, vista, x, y). Pontos entre âncoras são distribuídos no trajeto.
ANCHORS = {
    "P": [(1, F, 114, 138), (2, F, 110, 126), (3, F, 96, 170), (5, F, 80, 248), (7, F, 71, 333),
          (9, F, 69, 350), (10, F, 66, 368), (11, F, 60, 398)],
    "IG": [(1, F, 63, 402), (4, F, 66, 378), (5, F, 66, 352), (10, F, 76, 268), (11, F, 79, 250),
           (14, F, 90, 190), (15, F, 98, 130), (16, F, 104, 122), (17, F, 138, 112), (18, F, 136, 104),
           (19, F, 145, 80), (20, F, 141, 74)],
    "E": [(1, F, 138, 64), (2, F, 138, 70), (3, F, 139, 76), (4, F, 141, 88), (5, F, 133, 98),
          (6, F, 126, 92), (7, F, 122, 72), (8, F, 125, 34), (9, F, 140, 108), (11, F, 142, 121),
          (12, F, 124, 124), (13, F, 128, 130), (17, F, 128, 175), (18, F, 128, 190), (19, F, 134, 208),
          (25, F, 137, 262), (30, F, 138, 322), (31, F, 128, 350), (34, F, 126, 480), (35, F, 126, 505),
          (36, F, 125, 530), (40, F, 119, 580), (41, F, 122, 652), (42, F, 121, 665), (44, F, 118, 690),
          (45, F, 117, 698)],
    "BP": [(1, F, 128, 697), (3, F, 132, 678), (5, F, 135, 656), (6, F, 138, 620), (9, F, 140, 515),
           (10, F, 142, 470), (11, F, 142, 410), (12, F, 136, 338), (13, F, 130, 325), (15, F, 122, 262),
           (16, F, 121, 225), (17, F, 114, 192), (20, F, 113, 140), (21, F, 108, 215)],
    "C": [(1, F, 104, 150), (2, F, 96, 200), (3, F, 92, 250), (4, F, 80, 330), (7, F, 77, 350),
          (8, F, 75, 376), (9, F, 72, 404)],
    "ID": [(1, K, 72, 404), (3, K, 75, 380), (5, K, 77, 352), (6, K, 76, 340), (8, K, 92, 252),
           (9, K, 104, 152), (10, K, 108, 135), (11, K, 118, 165), (12, K, 118, 140), (13, K, 128, 142),
           (14, K, 136, 132), (15, K, 140, 125), (16, K, 132, 108), (17, F, 124, 98), (18, F, 132, 80),
           (19, F, 119, 64)],
    "B": [(1, F, 144, 58), (2, F, 143, 48), (3, F, 144, 32), (5, F, 144, 24), (6, K, 144, 24),
          (7, K, 144, 32), (9, K, 143, 58), (10, K, 142, 98), (11, K, 140, 128), (13, K, 140, 148),
          (15, K, 140, 170), (17, K, 140, 195), (20, K, 140, 232), (23, K, 140, 262), (25, K, 140, 285),
          (27, K, 142, 305), (30, K, 143, 328), (31, K, 145, 310), (34, K, 146, 334), (35, K, 147, 345),
          (36, K, 128, 365), (37, K, 128, 420), (38, K, 120, 492), (39, K, 116, 505), (40, K, 124, 505),
          (41, K, 126, 138), (43, K, 126, 160), (47, K, 126, 210), (52, K, 126, 262), (53, K, 128, 315),
          (54, K, 128, 338), (55, K, 124, 535), (57, K, 124, 580), (58, K, 118, 600), (60, K, 114, 652),
          (62, K, 113, 665), (64, K, 110, 680), (67, K, 108, 698)],
    "R": [(1, K, 122, 690), (2, F, 133, 684), (3, F, 137, 655), (6, F, 136, 668), (7, F, 139, 625),
          (9, F, 141, 585), (10, F, 142, 505), (11, F, 145, 328), (16, F, 145, 262), (21, F, 145, 205),
          (22, F, 140, 198), (27, F, 138, 124)],
    "PC": [(1, F, 120, 172), (2, F, 100, 170), (3, F, 86, 250), (6, F, 73, 325), (7, F, 73, 350),
           (8, F, 70, 378), (9, F, 66, 408)],
    "TA": [(1, K, 69, 404), (3, K, 70, 378), (4, K, 71, 352), (5, K, 73, 325), (10, K, 84, 240),
           (14, K, 100, 130), (15, K, 112, 124), (16, K, 128, 104), (17, F, 118, 78), (20, F, 117, 52),
           (21, F, 121, 58), (23, F, 131, 50)],
    "VB": [(1, F, 129, 58), (2, F, 120, 66), (3, F, 122, 54), (8, F, 118, 38), (12, K, 121, 72),
           (13, F, 130, 30), (14, F, 137, 42), (15, F, 137, 28), (19, K, 135, 50), (20, K, 132, 86),
           (21, K, 118, 124), (22, F, 106, 165), (24, F, 124, 200), (25, F, 110, 240), (26, F, 110, 268),
           (29, F, 108, 330), (30, K, 113, 345), (31, F, 104, 420), (34, F, 108, 520), (39, F, 112, 630),
           (40, F, 114, 655), (41, F, 113, 678), (44, F, 110, 698)],
    "F": [(1, F, 126, 698), (2, F, 128, 688), (3, F, 128, 678), (4, F, 133, 660), (5, F, 139, 600),
          (7, F, 141, 520), (8, F, 142, 505), (9, F, 144, 450), (11, F, 141, 350), (12, F, 140, 338),
          (13, F, 114, 250), (14, F, 128, 190)],
    "VG": [(1, K, 150, 345), (2, K, 150, 330), (4, K, 150, 265), (9, K, 150, 195), (14, K, 150, 120),
           (16, K, 150, 90), (20, K, 150, 22), (21, F, 150, 22), (24, F, 150, 34), (25, F, 150, 74),
           (26, F, 150, 80), (28, F, 150, 87)],
    "VC": [(1, F, 150, 338), (2, F, 150, 330), (3, F, 150, 315), (4, F, 150, 300), (6, F, 150, 272),
           (8, F, 150, 262), (12, F, 150, 232), (14, F, 150, 212), (15, F, 150, 206), (17, F, 150, 175),
           (22, F, 150, 120), (23, F, 150, 104), (24, F, 150, 96)],
}


# ------------------------------------------------------------------ auriculoterapia
# Pontos mais usados da nomenclatura chinesa GB/T 13734-2008 (código, nome em português, x, y).
# Desenho da ORELHA DIREITA vista de lado (rosto à esquerda), em 240 x 340. Posições esquemáticas.
AURICULAR = [
    # Hélice (HX)
    ("HX1", "Centro da orelha (Ponto Zero)", 100, 170), ("HX2", "Reto", 80, 152), ("HX3", "Uretra", 82, 136),
    ("HX4", "Genitais externos", 88, 118), ("HX5", "Ânus", 98, 98), ("HX6,7i", "Ápice da orelha", 150, 38),
    ("HX8", "Nódulo", 206, 92), ("HX9", "Hélice 1", 214, 132), ("HX10", "Hélice 2", 212, 172),
    ("HX11", "Hélice 3", 200, 214), ("HX12", "Hélice 4", 186, 256),
    # Escafa (SF)
    ("SF1", "Dedos", 182, 74), ("SF1,2i", "Vento-corrente (alergia)", 190, 98), ("SF2", "Punho", 194, 116),
    ("SF3", "Cotovelo", 198, 140), ("SF4,5", "Ombro", 196, 176), ("SF6", "Clavícula", 188, 214),
    # Anti-hélice (AH)
    ("AH1", "Calcanhar", 160, 84), ("AH2", "Dedos do pé", 174, 74), ("AH3", "Tornozelo", 168, 94),
    ("AH4", "Joelho", 174, 114), ("AH5", "Quadril", 176, 140), ("AH6", "Nervo ciático", 142, 138),
    ("AH6a", "Simpático", 114, 120), ("AH7", "Glúteo", 162, 154), ("AH8", "Abdome", 168, 188),
    ("AH9", "Coluna lombossacra", 178, 184), ("AH10", "Tórax", 164, 210), ("AH11", "Coluna torácica", 174, 208),
    ("AH12", "Pescoço", 154, 234), ("AH13", "Coluna cervical", 164, 234),
    # Fossa triangular (TF)
    ("TF1", "Fossa triangular superior", 164, 96), ("TF2", "Genitais internos", 126, 112),
    ("TF3", "Fossa triangular média", 148, 108), ("TF4", "Shenmen", 166, 120), ("TF5", "Pelve", 158, 132),
    # Trago (TG)
    ("TG1", "Trago superior", 72, 198), ("TG2", "Trago inferior", 72, 228), ("TG1u", "Ouvido externo", 80, 186),
    ("TG1p", "Ápice do trago", 66, 204), ("TG2p", "Adrenal", 66, 226), ("TG1,2i", "Nariz externo", 64, 215),
    ("TG3", "Faringe e laringe", 80, 210), ("TG4", "Nariz interno", 81, 224),
    # Antítrago (AT)
    ("AT1", "Testa", 110, 252), ("AT2", "Têmpora", 124, 248), ("AT3", "Occipício", 140, 246),
    ("AT4", "Subcórtex", 124, 259), ("AT1,2,4i", "Ápice do antítrago", 130, 240), ("AT3,4i", "Tronco cerebral", 150, 252),
    # Concha (CO)
    ("CO1", "Boca", 92, 184), ("CO2", "Esôfago", 106, 182), ("CO3", "Cárdia", 120, 182), ("CO4", "Estômago", 138, 178),
    ("CO5", "Duodeno", 146, 166), ("CO6", "Intestino delgado", 128, 162), ("CO7", "Intestino grosso", 110, 160),
    ("CO6,7i", "Apêndice", 119, 160), ("CO8", "Ângulo da concha superior", 164, 156), ("CO9", "Bexiga", 154, 152),
    ("CO10", "Rim", 140, 144), ("CO9,10i", "Ureter", 147, 148), ("CO6,10i", "Centro da concha superior", 128, 150),
    ("CO11", "Pâncreas e vesícula", 162, 168), ("CO12", "Fígado", 160, 184), ("CO13", "Baço", 156, 200),
    ("CO14", "Pulmão", 116, 214), ("CO15", "Coração", 126, 204), ("CO16", "Traqueia", 108, 198),
    ("CO17", "Sanjiao (Triplo Aquecedor)", 104, 226), ("CO18", "Endócrino", 96, 238),
    # Lóbulo (LO) — dividido em 9 áreas
    ("LO1", "Dentes", 112, 280), ("LO2", "Língua", 136, 280), ("LO3", "Mandíbula", 160, 280),
    ("LO4", "Lóbulo anterior", 112, 298), ("LO5", "Olho", 134, 298), ("LO5,6i", "Bochecha", 150, 306),
    ("LO6", "Ouvido interno", 162, 296), ("LO7,8,9", "Amígdala", 136, 316),
]
AURICULAR_REGIONS = {"HX": "Hélice", "SF": "Escafa", "AH": "Anti-hélice", "TF": "Fossa triangular",
                     "TG": "Trago", "AT": "Antítrago", "CO": "Concha", "LO": "Lóbulo"}


def auricular_code(gb):
    return "OR-" + gb.replace(",", ".").upper()


def auricular_points():
    return [{"code": auricular_code(gb), "meridian": "OR", "number": i, "intl_code": gb, "pinyin": name,
             "view": "ear", "x": x, "y": y} for i, (gb, name, x, y) in enumerate(AURICULAR, start=1)]


def default_position(meridian, number):
    """Posição esquemática padrão de um ponto: (vista, x, y)."""
    meridian = CN_TO_PT.get(meridian, meridian)
    if meridian == "OR":
        _gb, _name, x, y = AURICULAR[number - 1]
        return "ear", x, y
    anchors = ANCHORS[meridian]
    for n, view, x, y in anchors:
        if n == number:
            return view, x, y
    before = max((a for a in anchors if a[0] < number), key=lambda a: a[0])
    after = min((a for a in anchors if a[0] > number), key=lambda a: a[0])
    t = (number - before[0]) / (after[0] - before[0])
    view = before[1] if t < 0.5 or before[1] == after[1] else after[1]
    return view, round(before[2] + (after[2] - before[2]) * t, 1), round(before[3] + (after[3] - before[3]) * t, 1)


def all_points():
    """Os 361 pontos, prontos para gravar no banco."""
    points = []
    for code, intl, *_ in MERIDIANS:
        cn = PT_TO_CN[code]
        for i, pinyin in enumerate(NAMES[code].split(), start=1):
            view, x, y = default_position(code, i)
            points.append({"code": f"{cn}{i}", "meridian": cn, "number": i, "intl_code": f"{intl}{i}",
                           "pinyin": pinyin, "view": view, "x": x, "y": y})
    return points


def meridians_json():
    return [{"code": PT_TO_CN[c], "intl": i, "name": n, "color": col, "element": el, "bilateral": b}
            for c, i, n, col, el, b in MERIDIANS] + [
        {"code": "OR", "intl": "GB/T 13734", "name": "Orelha (auriculoterapia)", "color": "#d9480f",
         "element": "—", "bilateral": False}]
