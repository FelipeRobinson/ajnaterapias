"""Dados técnicos padrão da MTC (classificações de livro-texto) usados na parte TEÓRICA do mapa.

Contém só classificações objetivas e padronizadas (qual ponto é Yuan, Luo, Shu-riacho etc.).
Textos clínicos (funções, indicações, sinais, causas…) NÃO vêm prontos: a clínica escreve.
"""

INTL_TO_PT = {"LU": "P", "LI": "IG", "ST": "E", "SP": "BP", "HT": "C", "SI": "ID", "BL": "B",
              "KI": "R", "PC": "PC", "TE": "TA", "GB": "VB", "LR": "F", "GV": "VG", "CV": "VC"}

# Cinco pontos Shu: Jing-poço, Ying-nascente, Shu-riacho, Jing-rio, He-mar
FIVE_SHU = {
    "P": (11, 10, 9, 8, 5), "IG": (1, 2, 3, 5, 11), "E": (45, 44, 43, 41, 36), "BP": (1, 2, 3, 5, 9),
    "C": (9, 8, 7, 4, 3), "ID": (1, 2, 3, 5, 8), "B": (67, 66, 65, 60, 40), "R": (1, 2, 3, 7, 10),
    "PC": (9, 8, 7, 5, 3), "TA": (1, 2, 3, 6, 10), "VB": (44, 43, 41, 38, 34), "F": (1, 2, 3, 4, 8),
}
YIN = {"P", "BP", "C", "R", "PC", "F"}
SHU_NAMES = ["Jing-Poço", "Ying-Nascente", "Shu-Riacho", "Jing-Rio", "He-Mar"]
ELEM_YIN = ["Madeira", "Fogo", "Terra", "Metal", "Água"]
ELEM_YANG = ["Metal", "Água", "Madeira", "Fogo", "Terra"]

YUAN = ["P9", "IG4", "E42", "BP3", "C7", "ID4", "B64", "R3", "PC7", "TA4", "VB40", "F3"]
LUO = ["P7", "IG6", "E40", "BP4", "C5", "ID7", "B58", "R4", "PC6", "TA5", "VB37", "F5", "VC15", "VG1", "BP21"]
XI = ["P6", "IG7", "E34", "BP8", "C6", "ID6", "B63", "R5", "PC4", "TA7", "VB36", "F6", "R8", "B59", "R9", "VB35"]
BACK_SHU = {"B13": "Pulmão", "B14": "Pericárdio", "B15": "Coração", "B18": "Fígado", "B19": "Vesícula Biliar",
            "B20": "Baço", "B21": "Estômago", "B22": "Triplo Aquecedor", "B23": "Rim", "B25": "Intestino Grosso",
            "B27": "Intestino Delgado", "B28": "Bexiga"}
FRONT_MU = {"P1": "Pulmão", "VC17": "Pericárdio", "VC14": "Coração", "F14": "Fígado", "VB24": "Vesícula Biliar",
            "F13": "Baço", "VC12": "Estômago", "VC5": "Triplo Aquecedor", "VB25": "Rim", "E25": "Intestino Grosso",
            "VC4": "Intestino Delgado", "VC3": "Bexiga"}
HUI = {"F13": "Órgãos Zang", "VC12": "Vísceras Fu", "VC17": "Qi", "B17": "Sangue", "VB34": "Tendões",
       "P9": "Vasos", "B11": "Ossos", "VB39": "Medula"}
OPENING = {"BP4": "Chong Mai", "PC6": "Yin Wei Mai", "ID3": "Du Mai", "B62": "Yang Qiao Mai",
           "TA5": "Yang Wei Mai", "VB41": "Dai Mai", "P7": "Ren Mai", "R6": "Yin Qiao Mai"}
LOWER_HE = {"E36": "Estômago", "E37": "Intestino Grosso", "E39": "Intestino Delgado", "B39": "Triplo Aquecedor",
            "B40": "Bexiga", "VB34": "Vesícula Biliar"}
WINDOW_OF_SKY = ["E9", "IG18", "TA16", "B10", "P3", "VC22", "VG16", "ID16", "ID17", "PC1"]


def default_categories():
    """{código: [categorias]} com as classificações padrão."""
    cats = {}
    add = lambda code, label: cats.setdefault(code, []).append(label)
    for m, nums in FIVE_SHU.items():
        elems = ELEM_YIN if m in YIN else ELEM_YANG
        for i, n in enumerate(nums):
            add(f"{m}{n}", f"{SHU_NAMES[i]} ({elems[i]})")
    for c in YUAN: add(c, "Yuan (fonte)")
    for c in LUO: add(c, "Luo (conexão)" if c != "BP21" else "Grande Luo do Baço")
    for c in XI: add(c, "Xi (acúmulo)")
    for c, o in BACK_SHU.items(): add(c, f"Shu do dorso – {o}")
    for c, o in FRONT_MU.items(): add(c, f"Mu frontal – {o}")
    for c, h in HUI.items(): add(c, f"Hui (influência) – {h}")
    for c, v in OPENING.items(): add(c, f"Abertura – {v}")
    for c, o in LOWER_HE.items(): add(c, f"He inferior – {o}")
    for c in WINDOW_OF_SKY: add(c, "Janela do Céu")
    return cats


# Diagnóstico pela língua: aspectos padrão observados (o significado e as fotos são da clínica).
TONGUE = {
    "Cor do corpo": ["Língua pálida", "Língua rosada (normal)", "Língua vermelha", "Ponta vermelha",
                     "Bordas vermelhas", "Língua vermelho-escura", "Língua púrpura", "Língua azulada"],
    "Forma": ["Língua inchada", "Marcas de dentes nas bordas", "Língua fina", "Fissuras", "Fissura central",
              "Língua rígida", "Língua desviada", "Língua trêmula", "Pontos vermelhos", "Manchas roxas"],
    "Saburra": ["Saburra branca fina (normal)", "Saburra branca espessa", "Saburra amarela", "Saburra gordurosa",
                "Saburra seca", "Saburra descascada (geográfica)", "Sem saburra", "Saburra cinza ou preta"],
    "Umidade": ["Língua úmida", "Língua seca", "Língua muito molhada"],
    "Veias sublinguais": ["Veias sublinguais distendidas", "Veias sublinguais escuras"],
}

# Diagnósticos da MTC: só os NOMES padrão por órgão (o conteúdo clínico é escrito pela clínica).
SYNDROMES = {
    "Pulmão": ["Deficiência de Qi do Pulmão", "Deficiência de Yin do Pulmão", "Invasão de Vento-Frio",
               "Invasão de Vento-Calor", "Fleuma-Umidade no Pulmão", "Calor no Pulmão"],
    "Coração": ["Deficiência de Qi do Coração", "Deficiência de Sangue do Coração", "Deficiência de Yin do Coração",
                "Fogo do Coração", "Estase de Sangue do Coração"],
    "Baço": ["Deficiência de Qi do Baço", "Deficiência de Yang do Baço", "Baço não controla o Sangue",
             "Umidade-Frio no Baço", "Umidade-Calor no Baço"],
    "Estômago": ["Deficiência de Yin do Estômago", "Fogo no Estômago", "Retenção de alimentos",
                 "Contrafluxo do Qi do Estômago"],
    "Fígado": ["Estagnação do Qi do Fígado", "Ascensão do Yang do Fígado", "Fogo do Fígado",
               "Deficiência de Sangue do Fígado", "Vento interno do Fígado", "Umidade-Calor no Fígado e Vesícula"],
    "Rim": ["Deficiência de Yin do Rim", "Deficiência de Yang do Rim", "Deficiência de Essência (Jing) do Rim",
            "Qi do Rim não firme", "Rim não recebe o Qi"],
    "Padrões combinados": ["Desarmonia entre Coração e Rim", "Deficiência de Qi e Sangue", "Fígado invadindo o Baço",
                           "Estase de Sangue", "Fleuma"],
}
