"""
競馬場コードと競馬タイプの定義
"""

# Race types
RACE_TYPE_CENTRAL = "central"
RACE_TYPE_LOCAL = "local"
RACE_TYPE_BANEI = "banei"

VALID_RACE_TYPES = {RACE_TYPE_CENTRAL, RACE_TYPE_LOCAL, RACE_TYPE_BANEI}

# 中央競馬 (JRA) - 10場
CENTRAL_COURSE_CODES = {
    "01": "札幌",
    "02": "函館",
    "03": "福島",
    "04": "新潟",
    "05": "東京",
    "06": "中山",
    "07": "中京",
    "08": "京都",
    "09": "阪神",
    "10": "小倉",
}

# 地方競馬 (NAR) - 現存する14場
LOCAL_COURSE_CODES = {
    "30": "門別",
    "35": "盛岡",
    "36": "水沢",
    "42": "浦和",
    "43": "船橋",
    "44": "大井",
    "45": "川崎",
    "46": "金沢",
    "47": "笠松",
    "48": "名古屋",
    "50": "園田",
    "51": "姫路",
    "54": "高知",
    "55": "佐賀",
}

# ばんえい競馬
# nar.netkeiba.comはコード65、db.netkeiba.comはコード83を使用
BANEI_COURSE_CODES = {
    "65": "帯広",  # nar.netkeiba.com
    "83": "帯広",  # db.netkeiba.com（レース詳細ページ用）
}

# 全競馬場コード
ALL_COURSE_CODES = {**CENTRAL_COURSE_CODES, **LOCAL_COURSE_CODES, **BANEI_COURSE_CODES}


def get_race_type_from_course_code(course_code: str) -> str:
    """競馬場コードから競馬タイプを判定"""
    if course_code in CENTRAL_COURSE_CODES:
        return RACE_TYPE_CENTRAL
    elif course_code in LOCAL_COURSE_CODES:
        return RACE_TYPE_LOCAL
    elif course_code in BANEI_COURSE_CODES:
        return RACE_TYPE_BANEI
    else:
        # デフォルトは中央競馬として扱う
        return RACE_TYPE_CENTRAL


def get_course_name(course_code: str) -> str:
    """競馬場コードから競馬場名を取得"""
    return ALL_COURSE_CODES.get(course_code, "")


def is_central_race(race_id: str) -> bool:
    """race_idから中央競馬かどうかを判定"""
    if len(race_id) >= 6:
        course_code = race_id[4:6]
        return course_code in CENTRAL_COURSE_CODES
    return False


def is_local_race(race_id: str) -> bool:
    """race_idから地方競馬かどうかを判定"""
    if len(race_id) >= 6:
        course_code = race_id[4:6]
        return course_code in LOCAL_COURSE_CODES
    return False


def is_banei_race(race_id: str) -> bool:
    """race_idからばんえい競馬かどうかを判定"""
    if len(race_id) >= 6:
        course_code = race_id[4:6]
        return course_code in BANEI_COURSE_CODES
    return False
