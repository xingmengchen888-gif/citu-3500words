from flask import Flask, render_template, jsonify, request
import csv
import hashlib
import re
import sqlite3
import unicodedata
from pathlib import Path
from datetime import date, timedelta

app = Flask(__name__)


# =========================================================
# 路径
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "03_data"

DB_FILE = DATA_DIR / "vocabulary.db"
WORD_LIST_FILE = DATA_DIR / "wordlist.txt"
ECDICT_CSV_FILE = DATA_DIR / "ecdict.csv"


# =========================================================
# SQLite 基础工具
# =========================================================

def get_db():

    conn = sqlite3.connect(DB_FILE)

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# 初始化数据库
# =========================================================

def init_database():

    DATA_DIR.mkdir(exist_ok=True)

    conn = get_db()

    cursor = conn.cursor()

    # -----------------------------------------------------
    # 单词表
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY,
            word TEXT NOT NULL,
            pos TEXT,
            phonetic TEXT,
            meaning TEXT,
            example TEXT,
            example_cn TEXT,
            level TEXT,
            definition TEXT,
            translation TEXT,
            exchange TEXT,
            tag TEXT,
            bnc INTEGER DEFAULT 0,
            frq INTEGER DEFAULT 0,
            collins INTEGER DEFAULT 0,
            oxford INTEGER DEFAULT 0,
            detail TEXT,
            audio TEXT,
            matched_word TEXT,
            in_ecdict INTEGER DEFAULT 0
        )
    """)

    # -----------------------------------------------------
    # 词书表
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS word_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            words TEXT NOT NULL,
            is_system INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # -----------------------------------------------------
    # 学习进度表
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS word_progress (
            word_id INTEGER PRIMARY KEY,
            level INTEGER DEFAULT 0,
            last_review TEXT,
            next_review TEXT,
            correct_count INTEGER DEFAULT 0,
            wrong_count INTEGER DEFAULT 0,
            learned INTEGER DEFAULT 0,
            in_wrong INTEGER DEFAULT 0,
            FOREIGN KEY (word_id) REFERENCES words(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS progress_store (
            word_key TEXT PRIMARY KEY,
            word TEXT NOT NULL,
            level INTEGER DEFAULT 0,
            last_review TEXT,
            next_review TEXT,
            correct_count INTEGER DEFAULT 0,
            wrong_count INTEGER DEFAULT 0,
            learned INTEGER DEFAULT 0,
            in_wrong INTEGER DEFAULT 0
        )
    """)
    # -----------------------------------------------------
    # 学习日志表
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            study_date TEXT NOT NULL,
            study_type TEXT NOT NULL,
            result TEXT NOT NULL,
            FOREIGN KEY (word_id) REFERENCES words(id)
        )
    """)

    # -----------------------------------------------------
    # 系统配置表
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()

    # -----------------------------------------------------
    # 兼容旧版本数据库
    # -----------------------------------------------------

    # 检查 words 表是否已经有 pos 字段
    cursor.execute("""
        PRAGMA table_info(words)
    """)

    word_columns = {
        row["name"]
        for row in cursor.fetchall()
    }

    if "pos" not in word_columns:

        cursor.execute("""
            ALTER TABLE words
            ADD COLUMN pos TEXT
        """)

    # 检查 word_progress 表字段
    cursor.execute("""
        PRAGMA table_info(word_progress)
    """)

    columns = {
        row["name"]
        for row in cursor.fetchall()
    }

    if "learned" not in columns:

        cursor.execute("""
            ALTER TABLE word_progress
            ADD COLUMN learned INTEGER DEFAULT 0
        """)

    if "in_wrong" not in columns:

        cursor.execute("""
            ALTER TABLE word_progress
            ADD COLUMN in_wrong INTEGER DEFAULT 0
        """)

    # -----------------------------------------------------
    # 兼容旧版 words 表，补充 ECDICT 字段
    # -----------------------------------------------------

    cursor.execute("""
        PRAGMA table_info(words)
    """)

    word_columns = {
        row["name"]
        for row in cursor.fetchall()
    }

    ecdict_word_columns = {
        "definition": "TEXT",
        "translation": "TEXT",
        "exchange": "TEXT",
        "tag": "TEXT",
        "bnc": "INTEGER DEFAULT 0",
        "frq": "INTEGER DEFAULT 0",
        "collins": "INTEGER DEFAULT 0",
        "oxford": "INTEGER DEFAULT 0",
        "detail": "TEXT",
        "audio": "TEXT",
        "matched_word": "TEXT",
        "in_ecdict": "INTEGER DEFAULT 0"
    }

    for column_name, column_type in ecdict_word_columns.items():

        if column_name not in word_columns:

            cursor.execute(
                f"ALTER TABLE words "
                f"ADD COLUMN {column_name} {column_type}"
            )

    sync_progress_store(cursor)

    conn.commit()

    conn.close()


# =========================================================
# 自定义词表 + ECDICT 导入
#
# wordlist.txt 决定要学习的单词及顺序。
# ecdict.csv 提供音标、中英释义、词形变化等词典数据。
# =========================================================


ECDICT_ALIASES = {
    "relevent": "relevant",
    "sideroad": "side road",
    "mosquiton": "mosquito"
}


def normalize_word_key(value):

    text = unicodedata.normalize(
        "NFKC",
        str(value or "")
    )

    text = text.strip().lower().replace(
        "’",
        "'"
    )

    return re.sub(
        r"\s+",
        " ",
        text
    )


def compact_word_key(value):

    return re.sub(
        r"[^a-z0-9]+",
        "",
        normalize_word_key(value)
    )


def word_lookup_keys(value):

    normalized = normalize_word_key(value)

    aliased = ECDICT_ALIASES.get(
        normalized,
        normalized
    )

    keys = [
        normalized,
        aliased,
        compact_word_key(normalized),
        compact_word_key(aliased)
    ]

    return [
        key
        for key in dict.fromkeys(keys)
        if key
    ]


def clean_wordlist_entry(value):
    """兼容旧 words.json 中混入的词性、编号和乱码。"""

    text = unicodedata.normalize(
        "NFKC",
        str(value or "").strip()
    )

    text = re.sub(
        r"\s*[（(].*$",
        "",
        text
    )

    text = re.sub(
        r"(?<=\D)\d+",
        " ",
        text
    )

    text = re.sub(
        r"[^\x00-\x7F]+.*$",
        "",
        text
    )

    text = re.sub(
        r"[^A-Za-z\s.'-]+.*$",
        "",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip(" .")

    text = re.sub(
        r"\s+(?:n|v|vi|vt|adj|adv|prep|pron|conj|num|art|modal|aux|int)\.?$",
        "",
        text,
        flags=re.IGNORECASE
    )

    return text.strip(" .")


def legacy_word_lookup_keys(value):

    return word_lookup_keys(
        clean_wordlist_entry(value)
    )


def clean_ecdict_text(value):

    text = str(value or "")

    text = text.replace(
        "\\r\\n",
        "\n"
    ).replace(
        "\\n",
        "\n"
    ).replace(
        "\r\n",
        "\n"
    )

    return text.strip()


def derive_pos(translation, row_pos=""):

    if str(row_pos or "").strip():

        return str(row_pos).strip()

    labels = {
        "n": "n.",
        "v": "v.",
        "vi": "vi.",
        "vt": "vt.",
        "a": "adj.",
        "adj": "adj.",
        "ad": "adv.",
        "adv": "adv.",
        "prep": "prep.",
        "pron": "pron.",
        "conj": "conj.",
        "num": "num.",
        "art": "art.",
        "aux": "aux.",
        "modal": "modal"
    }

    result = []

    for match in re.finditer(
        r"(?m)^\s*([A-Za-z]+)\.",
        translation or ""
    ):

        key = match.group(1).lower()

        if key in labels and labels[key] not in result:

            result.append(labels[key])

    return " ".join(result)


def to_int(value, default=0):

    try:

        return int(value)

    except (TypeError, ValueError):

        return default


def ecdict_match_score(custom_word, row):

    row_word = row.get("word", "")

    return (
        1 if normalize_word_key(row_word) == normalize_word_key(custom_word) else 0,
        1 if compact_word_key(row_word) == compact_word_key(custom_word) else 0,
        1 if clean_ecdict_text(row.get("translation")) else 0,
        1 if clean_ecdict_text(row.get("definition")) else 0,
        1 if clean_ecdict_text(row.get("phonetic")) else 0,
        1 if clean_ecdict_text(row.get("tag")) else 0
    )


def normalize_word_list(raw_words, max_words=20000):
    """清理词表：忽略空行/注释，按大小写不敏感去重。"""

    if isinstance(raw_words, str):
        lines = raw_words.splitlines()
    else:
        lines = list(raw_words or [])

    words = []
    seen = set()

    for raw_word in lines:

        word = str(raw_word or "").strip()

        if not word or word.startswith("#"):
            continue

        word = unicodedata.normalize("NFKC", word)
        key = normalize_word_key(word)

        if not key or key in seen:
            continue

        seen.add(key)
        words.append(word)

        if len(words) > max_words:
            raise ValueError(f"词书最多支持 {max_words} 个单词")

    return words


def serialize_word_list(words):

    return "\n".join(words) + "\n"


def read_custom_wordlist():

    if not WORD_LIST_FILE.exists():
        raise FileNotFoundError(f"找不到自定义词表：{WORD_LIST_FILE}")

    words = normalize_word_list(
        WORD_LIST_FILE.read_text(encoding="utf-8-sig")
    )

    if not words:
        raise ValueError(f"自定义词表为空：{WORD_LIST_FILE}")

    return words


def get_active_word_book(cursor):

    cursor.execute("""
        SELECT
            b.id,
            b.name,
            b.words,
            b.is_system,
            b.created_at,
            b.updated_at
        FROM word_books b
        INNER JOIN app_meta meta
            ON CAST(b.id AS TEXT) = meta.value
        WHERE meta.key = 'active_word_book_id'
        LIMIT 1
    """)

    row = cursor.fetchone()

    if row is not None:
        return row

    cursor.execute("""
        SELECT
            id,
            name,
            words,
            is_system,
            created_at,
            updated_at
        FROM word_books
        WHERE is_system = 1
        ORDER BY id
        LIMIT 1
    """)

    row = cursor.fetchone()

    if row is None:
        raise RuntimeError("数据库中没有可用词书")

    cursor.execute("""
        INSERT OR REPLACE INTO app_meta (key, value)
        VALUES ('active_word_book_id', ?)
    """, (str(row["id"]),))

    return row


def get_word_book(cursor, book_id):

    cursor.execute("""
        SELECT
            id,
            name,
            words,
            is_system,
            created_at,
            updated_at
        FROM word_books
        WHERE id = ?
    """, (book_id,))

    return cursor.fetchone()


def word_book_to_dict(row, active_book_id=None, include_words=False):

    words = normalize_word_list(row["words"])

    result = {
        "id": row["id"],
        "name": row["name"],
        "word_count": len(words),
        "is_system": bool(row["is_system"]),
        "active": row["id"] == active_book_id,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

    if include_words:
        result["words"] = serialize_word_list(words)

    return result


def list_word_books(cursor):

    cursor.execute("""
        SELECT
            id,
            name,
            words,
            is_system,
            created_at,
            updated_at
        FROM word_books
        ORDER BY
            is_system DESC,
            id ASC
    """)

    rows = cursor.fetchall()
    active_book = get_active_word_book(cursor)

    return [
        word_book_to_dict(row, active_book["id"])
        for row in rows
    ]


def set_active_word_book(cursor, book_id):

    cursor.execute("""
        INSERT OR REPLACE INTO app_meta (key, value)
        VALUES ('active_word_book_id', ?)
    """, (str(book_id),))


def sync_progress_store(cursor):
    """把当前词书的学习状态保存到全局进度表。"""

    cursor.execute("""
        SELECT
            w.word,
            p.level,
            p.last_review,
            p.next_review,
            p.correct_count,
            p.wrong_count,
            p.learned,
            p.in_wrong
        FROM word_progress p
        INNER JOIN words w
            ON w.id = p.word_id
    """)

    for row in cursor.fetchall():

        cursor.execute("""
            INSERT OR REPLACE INTO progress_store (
                word_key,
                word,
                level,
                last_review,
                next_review,
                correct_count,
                wrong_count,
                learned,
                in_wrong
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            normalize_word_key(row["word"]),
            row["word"],
            row["level"],
            row["last_review"],
            row["next_review"],
            row["correct_count"],
            row["wrong_count"],
            row["learned"],
            row["in_wrong"]
        ))


def sync_system_wordbook():

    words = read_custom_wordlist()
    words_text = serialize_word_list(words)
    today = date.today().isoformat()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM word_books
        WHERE is_system = 1
        ORDER BY id
        LIMIT 1
    """)

    row = cursor.fetchone()

    if row is None:

        cursor.execute("""
            INSERT INTO word_books (
                name,
                words,
                is_system,
                created_at,
                updated_at
            )
            VALUES (?, ?, 1, ?, ?)
        """, (
            "高考3500词",
            words_text,
            today,
            today
        ))

        book_id = cursor.lastrowid

    else:

        book_id = row["id"]

        cursor.execute("""
            UPDATE word_books
            SET words = ?, updated_at = ?
            WHERE id = ?
        """, (
            words_text,
            today,
            book_id
        ))

    cursor.execute("""
        SELECT value
        FROM app_meta
        WHERE key = 'active_word_book_id'
    """)

    active_row = cursor.fetchone()

    if active_row is None:

        set_active_word_book(cursor, book_id)

    conn.commit()
    conn.close()

    return book_id


ECDICT_MATCH_CACHE = {}
ECDICT_CACHE_SOURCE = None


def load_ecdict_matches(words):

    global ECDICT_CACHE_SOURCE

    if not ECDICT_CSV_FILE.exists():
        raise FileNotFoundError(
            f"找不到 ECDICT 数据文件：{ECDICT_CSV_FILE}"
        )

    stat = ECDICT_CSV_FILE.stat()
    source = (stat.st_size, stat.st_mtime_ns)

    if source != ECDICT_CACHE_SOURCE:

        ECDICT_MATCH_CACHE.clear()
        ECDICT_CACHE_SOURCE = source

    missing_words = [
        word
        for word in words
        if word not in ECDICT_MATCH_CACHE
    ]

    if missing_words:

        target_keys = {}

        for word in missing_words:

            for key in word_lookup_keys(word):

                target_keys.setdefault(key, set()).add(word)

        matches = {}

        with open(
            ECDICT_CSV_FILE,
            "r",
            encoding="utf-8",
            newline=""
        ) as handle:

            reader = csv.DictReader(handle)

            for row in reader:

                row_word = row.get("word", "")
                exact_key = normalize_word_key(row_word)
                compact_key = compact_word_key(row_word)

                candidates = set()

                candidates.update(
                    target_keys.get(exact_key, ())
                )

                if compact_key != exact_key:

                    candidates.update(
                        target_keys.get(compact_key, ())
                    )

                for custom_word in candidates:

                    score = ecdict_match_score(custom_word, row)
                    current = matches.get(custom_word)

                    if current is None or score > current[0]:

                        matches[custom_word] = (score, row)

        for word in missing_words:

            result = matches.get(word)

            ECDICT_MATCH_CACHE[word] = (
                result[1]
                if result is not None
                else None
            )

    return {
        word: ECDICT_MATCH_CACHE.get(word)
        for word in words
    }


def get_ecdict_import_signature(book_id, words):

    stat = ECDICT_CSV_FILE.stat()
    wordlist_digest = hashlib.sha256(
        serialize_word_list(words).encode("utf-8")
    ).hexdigest()

    return (
        f"{book_id}:"
        f"{wordlist_digest}:"
        f"{stat.st_size}:"
        f"{stat.st_mtime_ns}"
    )


def import_ecdict_words(force=False):
    """按当前词书重建 words 表，并保留单词对应的学习进度。"""

    conn = get_db()
    cursor = conn.cursor()

    book = get_active_word_book(cursor)
    words = normalize_word_list(book["words"])

    if not words:
        conn.close()
        raise ValueError(f"词书“{book['name']}”为空")

    signature = get_ecdict_import_signature(book["id"], words)

    cursor.execute("""
        SELECT value
        FROM app_meta
        WHERE key = 'ecdict_import_signature'
    """)

    signature_row = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM words")
    current_count = cursor.fetchone()[0]

    if (
        not force
        and signature_row
        and signature_row["value"] == signature
        and current_count == len(words)
    ):

        conn.close()
        return

    matches = load_ecdict_matches(words)

    new_id_by_key = {}

    for index, word in enumerate(words, start=1):

        for key in word_lookup_keys(word):

            new_id_by_key.setdefault(key, index)

    id_map = {}

    cursor.execute("SELECT id, word FROM words")
    old_word_rows = cursor.fetchall()

    for row in old_word_rows:

        new_id = None

        for key in legacy_word_lookup_keys(row["word"]):

            if key in new_id_by_key:

                new_id = new_id_by_key[key]
                break

        if new_id is not None:

            id_map[row["id"]] = new_id

    sync_progress_store(cursor)

    stored_progress = {
        row["word_key"]: row
        for row in cursor.execute("""
            SELECT
                word_key,
                level,
                last_review,
                next_review,
                correct_count,
                wrong_count,
                learned,
                in_wrong
            FROM progress_store
        """)
    }

    progress_snapshot = []

    for index, word in enumerate(words, start=1):

        stored = stored_progress.get(
            normalize_word_key(word)
        )

        if stored is None:
            continue

        progress_row = dict(stored)
        progress_row["word_id"] = index
        progress_snapshot.append(progress_row)

    try:

        cursor.execute("DELETE FROM word_progress")
        cursor.execute("DELETE FROM words")

        matched_count = 0

        for index, word in enumerate(words, start=1):

            row = matches.get(word)

            if row is None:
                row = {}
            else:
                matched_count += 1

            translation = clean_ecdict_text(row.get("translation"))
            definition = clean_ecdict_text(row.get("definition"))
            meaning = translation or definition or "暂无释义"
            phonetic = clean_ecdict_text(row.get("phonetic"))
            pos = derive_pos(translation, row.get("pos"))

            cursor.execute("""
                INSERT INTO words (
                    id,
                    word,
                    pos,
                    phonetic,
                    meaning,
                    example,
                    example_cn,
                    level,
                    definition,
                    translation,
                    exchange,
                    tag,
                    bnc,
                    frq,
                    collins,
                    oxford,
                    detail,
                    audio,
                    matched_word,
                    in_ecdict
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                index,
                word,
                pos,
                phonetic,
                meaning,
                "",
                "",
                "高中",
                definition,
                translation,
                clean_ecdict_text(row.get("exchange")),
                clean_ecdict_text(row.get("tag")),
                to_int(row.get("bnc")),
                to_int(row.get("frq")),
                to_int(row.get("collins")),
                to_int(row.get("oxford")),
                clean_ecdict_text(row.get("detail")),
                clean_ecdict_text(row.get("audio")),
                clean_ecdict_text(row.get("word")),
                1 if row else 0
            ))

        for row in progress_snapshot:

            cursor.execute("""
                INSERT OR REPLACE INTO word_progress (
                    word_id,
                    level,
                    last_review,
                    next_review,
                    correct_count,
                    wrong_count,
                    learned,
                    in_wrong
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["word_id"],
                row["level"],
                row["last_review"],
                row["next_review"],
                row["correct_count"],
                row["wrong_count"],
                row["learned"],
                row["in_wrong"]
            ))

        for old_id, new_id in id_map.items():

            if old_id == new_id:
                continue

            cursor.execute("""
                UPDATE study_log
                SET word_id = ?
                WHERE word_id = ?
            """, (new_id, old_id))

        cursor.execute("""
            INSERT OR REPLACE INTO app_meta (key, value)
            VALUES ('ecdict_import_signature', ?)
        """, (signature,))

        cursor.execute("""
            INSERT OR REPLACE INTO app_meta (key, value)
            VALUES ('ecdict_word_count', ?)
        """, (str(len(words)),))

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()

    print(
        f"ECDICT 导入完成：词书“{book['name']}”，"
        f"{len(words)} 个单词，匹配 {matched_count} 条词典数据"
    )


# =========================================================
# 单词查询
# =========================================================

def get_all_words():

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            word,
            pos,
            phonetic,
            meaning,
            example,
            example_cn,
            level
        FROM words
        ORDER BY id
    """)

    rows = cursor.fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# 首页
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# 获取全部单词
# =========================================================

@app.route("/api/words")
def get_words():

    words = get_all_words()

    return jsonify(words)


# =========================================================
# 词库：分页、搜索和状态筛选
# =========================================================

@app.route("/api/library")
def get_word_library():

    try:

        page = int(
            request.args.get(
                "page",
                1
            )
        )

    except (TypeError, ValueError):

        page = 1

    try:

        per_page = int(
            request.args.get(
                "per_page",
                40
            )
        )

    except (TypeError, ValueError):

        per_page = 40

    page = max(page, 1)

    per_page = min(
        max(per_page, 1),
        100
    )

    query = request.args.get(
        "q",
        ""
    ).strip()

    status = request.args.get(
        "status",
        "all"
    ).strip()

    if status not in (
        "all",
        "new",
        "learning",
        "mastered",
        "wrong"
    ):

        status = "all"

    where_parts = []

    params = []

    if query:

        like = f"%{query}%"

        where_parts.append("""
            (
                LOWER(w.word) LIKE LOWER(?)
                OR LOWER(COALESCE(w.meaning, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(w.translation, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(w.tag, '')) LIKE LOWER(?)
            )
        """)

        params.extend([
            like,
            like,
            like,
            like
        ])

    if status == "new":

        where_parts.append("p.word_id IS NULL")

    elif status == "learning":

        where_parts.append("""
            p.word_id IS NOT NULL
            AND p.in_wrong = 0
            AND p.level < 3
        """)

    elif status == "mastered":

        where_parts.append("""
            p.word_id IS NOT NULL
            AND p.in_wrong = 0
            AND p.level >= 3
        """)

    elif status == "wrong":

        where_parts.append("""
            p.word_id IS NOT NULL
            AND p.in_wrong = 1
        """)

    where_sql = ""

    if where_parts:

        where_sql = "WHERE " + " AND ".join(
            where_parts
        )

    base_sql = """
        FROM words w
        LEFT JOIN word_progress p
            ON w.id = p.word_id
    """

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute(
        f"SELECT COUNT(*) {base_sql} {where_sql}",
        params
    )

    total = cursor.fetchone()[0]

    total_pages = max(
        (total + per_page - 1) // per_page,
        1
    )

    page = min(
        page,
        total_pages
    )

    offset = (page - 1) * per_page

    cursor.execute(
        f"""
        SELECT
            w.id,
            w.word,
            w.pos,
            w.phonetic,
            COALESCE(NULLIF(w.translation, ''), NULLIF(w.meaning, ''), '') AS meaning,
            w.definition,
            w.translation,
            w.exchange,
            w.tag,
            w.bnc,
            w.frq,
            w.collins,
            w.oxford,
            w.detail,
            w.audio,
            w.matched_word,
            w.in_ecdict,
            COALESCE(p.level, 0) AS level,
            COALESCE(p.learned, 0) AS learned,
            COALESCE(p.in_wrong, 0) AS in_wrong,
            COALESCE(p.correct_count, 0) AS correct_count,
            COALESCE(p.wrong_count, 0) AS wrong_count,
            p.next_review,
            CASE
                WHEN p.word_id IS NULL THEN 'new'
                WHEN p.in_wrong = 1 THEN 'wrong'
                WHEN p.level >= 3 THEN 'mastered'
                ELSE 'learning'
            END AS progress_status
        {base_sql}
        {where_sql}
        ORDER BY w.id
        LIMIT ? OFFSET ?
        """,
        params + [per_page, offset]
    )

    rows = cursor.fetchall()

    active_book = get_active_word_book(cursor)

    wordbook = word_book_to_dict(
        active_book,
        active_book["id"]
    )

    wordbooks = list_word_books(cursor)

    conn.close()

    words = []

    for row in rows:

        item = dict(row)

        for field in (
            "meaning",
            "definition",
            "translation",
            "detail"
        ):

            item[field] = clean_ecdict_text(
                item.get(field)
            )

        words.append(item)

    return jsonify({

        "success": True,

        "words": words,

        "total": total,

        "page": page,

        "per_page": per_page,

        "pages": total_pages,

        "query": query,

        "status": status,

        "wordbook": wordbook,

        "wordbooks": wordbooks

    })


# =========================================================
# 自定义词书管理
# =========================================================

MAX_WORD_BOOK_SIZE = 20000


@app.route("/api/wordbooks")
def get_word_books():

    conn = get_db()
    cursor = conn.cursor()

    wordbooks = list_word_books(cursor)

    conn.close()

    return jsonify({

        "success": True,

        "wordbooks": wordbooks

    })


@app.route("/api/wordbooks", methods=["POST"])
def create_word_book():

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    raw_words = data.get("words", "")

    if not name:

        return jsonify({
            "success": False,
            "message": "请输入词书名称"
        }), 400

    if len(name) > 40:

        return jsonify({
            "success": False,
            "message": "词书名称不能超过 40 个字符"
        }), 400

    try:

        words = normalize_word_list(
            raw_words,
            MAX_WORD_BOOK_SIZE
        )

    except ValueError as error:

        return jsonify({
            "success": False,
            "message": str(error)
        }), 400

    if not words:

        return jsonify({
            "success": False,
            "message": "词书至少需要一个单词"
        }), 400

    today = date.today().isoformat()

    conn = get_db()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            INSERT INTO word_books (
                name,
                words,
                is_system,
                created_at,
                updated_at
            )
            VALUES (?, ?, 0, ?, ?)
        """, (
            name,
            serialize_word_list(words),
            today,
            today
        ))

        book_id = cursor.lastrowid

        set_active_word_book(cursor, book_id)

        conn.commit()

    except sqlite3.IntegrityError:

        conn.rollback()
        conn.close()

        return jsonify({
            "success": False,
            "message": "这个词书名称已经存在"
        }), 409

    conn.close()

    import_ecdict_words(force=True)

    conn = get_db()
    cursor = conn.cursor()
    book = get_word_book(cursor, book_id)
    wordbook = word_book_to_dict(book, book_id)
    conn.close()

    return jsonify({

        "success": True,

        "wordbook": wordbook,

        "message": "词书创建成功"

    })


@app.route(
    "/api/wordbooks/<int:book_id>",
    methods=["GET", "PUT"]
)
def word_book_detail(book_id):

    conn = get_db()
    cursor = conn.cursor()
    book = get_word_book(cursor, book_id)

    if book is None:

        conn.close()

        return jsonify({
            "success": False,
            "message": "找不到这个词书"
        }), 404

    if request.method == "GET":

        active_book = get_active_word_book(cursor)
        result = word_book_to_dict(
            book,
            active_book["id"],
            include_words=True
        )

        conn.close()

        return jsonify({
            "success": True,
            "wordbook": result
        })

    if book["is_system"]:

        conn.close()

        return jsonify({
            "success": False,
            "message": "默认词书请直接编辑 03_data/wordlist.txt"
        }), 400

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    raw_words = data.get("words", "")

    if not name:

        conn.close()

        return jsonify({
            "success": False,
            "message": "请输入词书名称"
        }), 400

    if len(name) > 40:

        conn.close()

        return jsonify({
            "success": False,
            "message": "词书名称不能超过 40 个字符"
        }), 400

    try:

        words = normalize_word_list(
            raw_words,
            MAX_WORD_BOOK_SIZE
        )

    except ValueError as error:

        conn.close()

        return jsonify({
            "success": False,
            "message": str(error)
        }), 400

    if not words:

        conn.close()

        return jsonify({
            "success": False,
            "message": "词书至少需要一个单词"
        }), 400

    active_book = get_active_word_book(cursor)
    is_active = active_book["id"] == book_id

    try:

        cursor.execute("""
            UPDATE word_books
            SET name = ?, words = ?, updated_at = ?
            WHERE id = ?
        """, (
            name,
            serialize_word_list(words),
            date.today().isoformat(),
            book_id
        ))

        conn.commit()

    except sqlite3.IntegrityError:

        conn.rollback()
        conn.close()

        return jsonify({
            "success": False,
            "message": "这个词书名称已经存在"
        }), 409

    conn.close()

    if is_active:

        import_ecdict_words(force=True)

    conn = get_db()
    cursor = conn.cursor()
    book = get_word_book(cursor, book_id)
    wordbook = word_book_to_dict(
        book,
        book_id if is_active else active_book["id"]
    )
    conn.close()

    return jsonify({

        "success": True,

        "wordbook": wordbook,

        "message": "词书已更新"

    })


@app.route(
    "/api/wordbooks/<int:book_id>/activate",
    methods=["POST"]
)
def activate_word_book(book_id):

    conn = get_db()
    cursor = conn.cursor()
    book = get_word_book(cursor, book_id)

    if book is None:

        conn.close()

        return jsonify({
            "success": False,
            "message": "找不到这个词书"
        }), 404

    set_active_word_book(cursor, book_id)
    conn.commit()
    conn.close()

    import_ecdict_words(force=True)

    conn = get_db()
    cursor = conn.cursor()
    book = get_word_book(cursor, book_id)
    wordbook = word_book_to_dict(book, book_id)
    conn.close()

    return jsonify({

        "success": True,

        "wordbook": wordbook,

        "message": f"已切换到“{wordbook['name']}”"

    })


@app.route(
    "/api/wordbooks/<int:book_id>",
    methods=["DELETE"]
)
def delete_word_book(book_id):

    conn = get_db()
    cursor = conn.cursor()
    book = get_word_book(cursor, book_id)

    if book is None:

        conn.close()

        return jsonify({
            "success": False,
            "message": "找不到这个词书"
        }), 404

    if book["is_system"]:

        conn.close()

        return jsonify({
            "success": False,
            "message": "默认词书不能删除"
        }), 400

    active_book = get_active_word_book(cursor)
    was_active = active_book["id"] == book_id

    cursor.execute("""
        DELETE FROM word_books
        WHERE id = ?
    """, (book_id,))

    if was_active:

        cursor.execute("""
            SELECT id
            FROM word_books
            WHERE is_system = 1
            ORDER BY id
            LIMIT 1
        """)

        system_book = cursor.fetchone()

        if system_book is not None:

            set_active_word_book(cursor, system_book["id"])

    conn.commit()
    conn.close()

    if was_active:

        import_ecdict_words(force=True)

    return jsonify({

        "success": True,

        "message": "词书已删除"

    })


# =========================================================
# 获取今日新词
#
# 新词 = 数据库中还没有学习记录的词
# =========================================================

@app.route("/api/today-words")
def get_today_words():

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            w.id,
            w.word,
            w.pos,
            w.phonetic,
            w.meaning,
            w.example,
            w.example_cn,
            w.level
        FROM words w
        LEFT JOIN word_progress p
            ON w.id = p.word_id
        WHERE p.word_id IS NULL
        ORDER BY w.id
        LIMIT 30
    """)

    rows = cursor.fetchall()

    conn.close()

    words = [
        dict(row)
        for row in rows
    ]

    return jsonify({

        "success": True,

        "count": len(words),

        "words": words

    })


# =========================================================
# 获取今日需要复习的单词
#
# next_review <= 今天
# =========================================================

@app.route("/api/review-words")
def get_review_words():

    today = date.today().isoformat()

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            w.id,
            w.word,
            w.pos,
            w.phonetic,
            w.meaning,
            w.example,
            w.example_cn,
            w.level
        FROM words w
        INNER JOIN word_progress p
            ON w.id = p.word_id
        WHERE p.next_review IS NOT NULL
          AND p.next_review <= ?
        ORDER BY
            p.next_review ASC,
            p.level ASC,
            w.id ASC
        LIMIT 45
    """, (today,))

    rows = cursor.fetchall()

    conn.close()

    words = [dict(row) for row in rows]

    return jsonify({
        "success": True,
        "count": len(words),
        "words": words
    })


# =========================================================
# 获取错词本
# =========================================================

@app.route("/api/wrong-words")
def get_wrong_words():

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            w.id,
            w.word,
            w.pos,
            w.phonetic,
            w.meaning,
            w.example,
            w.example_cn,
            w.level
        FROM words w
        INNER JOIN word_progress p
            ON w.id = p.word_id
        WHERE p.in_wrong = 1
        ORDER BY
            p.wrong_count DESC,
            w.id ASC
    """)

    rows = cursor.fetchall()

    conn.close()

    words = [
        dict(row)
        for row in rows
    ]

    return jsonify(words)


# =========================================================
# 获取学习统计
# =========================================================

@app.route("/api/stats")
def get_stats():

    conn = get_db()

    cursor = conn.cursor()

    # 总词数
    cursor.execute("""
        SELECT COUNT(*)
        FROM words
    """)

    total_words = cursor.fetchone()[0]

    # 已学习词数
    cursor.execute("""
        SELECT COUNT(*)
        FROM word_progress
        WHERE learned = 1
    """)

    learned_count = cursor.fetchone()[0]

    # 当前错词数量
    cursor.execute("""
        SELECT COUNT(*)
        FROM word_progress
        WHERE in_wrong = 1
    """)

    wrong_count = cursor.fetchone()[0]

    # 总学习次数
    cursor.execute("""
        SELECT value
        FROM app_meta
        WHERE key = 'total_studied'
    """)

    row = cursor.fetchone()

    total_studied = 0

    if row:

        try:

            total_studied = int(
                row["value"]
            )

        except (
            ValueError,
            TypeError
        ):

            total_studied = 0

    conn.close()

    remaining_count = max(
        total_words - learned_count,
        0
    )

    percentage = 0

    if total_words > 0:

        percentage = round(
            learned_count
            / total_words
            * 100,
            1
        )

    return jsonify({

        "total_words": total_words,

        "learned_count": learned_count,

        "wrong_count": wrong_count,

        "remaining_count": remaining_count,

        "percentage": percentage,

        "total_studied": total_studied

    })

# ========================================
# 详细统计
# ========================================

@app.route("/api/statistics")
def get_statistics():

    conn = get_db()

    cursor = conn.cursor()


    # 总词数

    cursor.execute("""
        SELECT COUNT(*)
        FROM words
    """)

    total_words = cursor.fetchone()[0]


    # 已学习

    cursor.execute("""
        SELECT COUNT(*)
        FROM word_progress
        WHERE correct_count > 0
    """)

    learned_words = cursor.fetchone()[0]


    # 掌握词汇(level >=3)

    cursor.execute("""
        SELECT COUNT(*)
        FROM word_progress
        WHERE level >= 3
    """)

    mastered_words = cursor.fetchone()[0]


    # 错词数量

    cursor.execute("""
        SELECT COUNT(*)
        FROM word_progress
        WHERE wrong_count > 0
    """)

    wrong_words = cursor.fetchone()[0]


    # 累计学习次数

    cursor.execute("""
        SELECT COUNT(*)
        FROM study_log
    """)

    total_study = cursor.fetchone()[0]


    # 今天学习

    today = date.today().isoformat()


    cursor.execute("""
        SELECT COUNT(*)
        FROM study_log
        WHERE study_date=?
    """,(today,))

    today_study = cursor.fetchone()[0]


    conn.close()


    return jsonify({

        "total_words":total_words,

        "learned_words":learned_words,

        "mastered_words":mastered_words,

        "wrong_words":wrong_words,

        "total_study":total_study,

        "today_study":today_study

    })
# =========================================================
# 今日学习进度
# =========================================================

@app.route("/api/today-progress")
def get_today_progress():

    today = date.today().isoformat()

    conn = get_db()
    cursor = conn.cursor()

    # =========================================
    # 今天已经完成的新词
    # =========================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM study_log
        WHERE study_date = ?
          AND study_type = '新词'
    """, (today,))

    new_completed = cursor.fetchone()[0]

    # =========================================
    # 今天已经完成的复习
    # =========================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM study_log
        WHERE study_date = ?
          AND study_type = '复习'
    """, (today,))

    review_completed = cursor.fetchone()[0]

    # =========================================
    # 今天实际可安排的新词
    # 最多30个
    # =========================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM words w
        LEFT JOIN word_progress p
            ON w.id = p.word_id
        WHERE p.word_id IS NULL
    """)

    all_new_words = cursor.fetchone()[0]

    new_total = min(
        30,
        new_completed + all_new_words
    )

    new_total = min(
        new_total,
        30
    )

    # =========================================
    # 今天剩余新词
    # =========================================

    new_remaining = max(
        new_total - new_completed,
        0
    )

    # =========================================
    # 今天原本到期的复习词
    # =========================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM word_progress
        WHERE next_review IS NOT NULL
          AND next_review <= ?
    """, (today,))

    review_remaining_raw = cursor.fetchone()[0]

    # =========================================
    # 每天最多安排45个复习词
    # =========================================

    review_remaining = min(
        review_remaining_raw,
        max(45 - review_completed, 0)
    )

    review_total = min(
        45,
        review_completed + review_remaining
    )

    # =========================================
    # 今日总完成
    # =========================================

    total_completed = (
        new_completed +
        review_completed
    )

    total_target = (
        new_total +
        review_total
    )

    # =========================================
    # 完成百分比
    # =========================================

    percentage = 0

    if total_target > 0:

        percentage = round(
            total_completed
            / total_target
            * 100,
            1
        )

    conn.close()

    return jsonify({

        "new_completed": new_completed,
        "new_total": new_total,
        "new_remaining": new_remaining,

        "review_completed": review_completed,
        "review_total": review_total,
        "review_remaining": review_remaining,

        "total_completed": total_completed,
        "total_target": total_target,

        "percentage": percentage

    })
# =========================================================
# 获取学习进度
#
# 保持和你之前 progress.json 类似的返回格式，
# 这样前端调试不会乱。
# =========================================================

@app.route("/api/progress")
def get_progress():

    conn = get_db()

    cursor = conn.cursor()

    # 已学习
    cursor.execute("""
        SELECT word_id
        FROM word_progress
        WHERE learned = 1
        ORDER BY word_id
    """)

    learned_ids = [
        row["word_id"]
        for row in cursor.fetchall()
    ]

    # 错词
    cursor.execute("""
        SELECT word_id
        FROM word_progress
        WHERE in_wrong = 1
        ORDER BY word_id
    """)

    wrong_ids = [
        row["word_id"]
        for row in cursor.fetchall()
    ]

    # 每个单词的复习记录
    cursor.execute("""
        SELECT
            word_id,
            level,
            last_review,
            next_review,
            correct_count,
            wrong_count
        FROM word_progress
        ORDER BY word_id
    """)

    rows = cursor.fetchall()

    word_progress = {}

    for row in rows:

        word_progress[str(
            row["word_id"]
        )] = {

            "level": row["level"],

            "last_review":
                row["last_review"],

            "next_review":
                row["next_review"],

            "correct_count":
                row["correct_count"],

            "wrong_count":
                row["wrong_count"]

        }

    # 总学习次数
    cursor.execute("""
        SELECT value
        FROM app_meta
        WHERE key = 'total_studied'
    """)

    total_row = cursor.fetchone()

    total_studied = 0

    if total_row:

        try:

            total_studied = int(
                total_row["value"]
            )

        except (
            ValueError,
            TypeError
        ):

            total_studied = 0

    conn.close()

    return jsonify({

        "learned_ids": learned_ids,

        "wrong_ids": wrong_ids,

        "total_studied": total_studied,

        "word_progress": word_progress

    })


# =========================================================
# 记录学习结果
#
# 认识：
#   learned = 1
#   in_wrong = 0
#   level + 1
#
# 不认识：
#   in_wrong = 1
#   level - 1
#   明天复习
# =========================================================

@app.route("/api/record", methods=["POST"])
def record_word():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({

            "success": False,

            "message": "没有收到数据"

        }), 400

    word_id = data.get(
        "word_id"
    )

    result = data.get(
        "result"
    )
    study_type = data.get("study_type")
    if word_id is None:

        return jsonify({

            "success": False,

            "message": "缺少 word_id"

        }), 400
    if study_type not in (
    "新词",
    "复习"
    ):

        return jsonify({

            "success": False,

            "message":"study_type 必须是 新词 或 复习"

        }), 400
    if result not in (
        "known",
        "unknown"
    ):

        return jsonify({

            "success": False,

            "message":
                "result 必须是 "
                "known 或 unknown"

        }), 400

    try:

        word_id = int(word_id)

    except (
        ValueError,
        TypeError
    ):

        return jsonify({

            "success": False,

            "message":
                "word_id 必须是数字"

        }), 400

    conn = get_db()

    cursor = conn.cursor()

    # 检查单词是否存在
    cursor.execute("""
        SELECT id, word
        FROM words
        WHERE id = ?
    """, (
        word_id,
    ))

    word_row = cursor.fetchone()

    if word_row is None:

        conn.close()

        return jsonify({

            "success": False,

            "message":
                "找不到这个单词"

        }), 404

    word_text = word_row["word"]

    # 查询现有进度
    cursor.execute("""
        SELECT *
        FROM word_progress
        WHERE word_id = ?
    """, (
        word_id,
    ))

    row = cursor.fetchone()

    if row:

        level = row["level"] or 0

        correct_count = (
            row["correct_count"] or 0
        )

        wrong_count = (
            row["wrong_count"] or 0
        )

        learned = (
            row["learned"] or 0
        )

        in_wrong = (
            row["in_wrong"] or 0
        )

    else:

        level = 0

        correct_count = 0

        wrong_count = 0

        learned = 0

        in_wrong = 0

    today = date.today()

    # =====================================================
    # 不认识
    # =====================================================

    if result == "unknown":

        wrong_count += 1

        level = max(
            level - 1,
            0
        )

        in_wrong = 1

        # 第一次就答错，也说明它已经学习过/测试过，
        # 所以以后不会再被当作“纯新词”。
        #
        # 但是 learned 保持原状态：
        # 如果以前已经认识过，不会因为一次错误
        # 就完全抹掉学习记录。
        #
        # 第一次就不认识：
        # learned 仍然是 0。

        last_review = today.isoformat()

        next_review = (
            today
            + timedelta(days=1)
        ).isoformat()

    # =====================================================
    # 认识
    # =====================================================

    else:

        correct_count += 1

        learned = 1

        # 一旦本次认识，
        # 就不再属于当前错词本。
        in_wrong = 0

        level = min(
            level + 1,
            5
        )

        last_review = today.isoformat()

        review_intervals = {

            1: 1,

            2: 3,

            3: 7,

            4: 15,

            5: 30

        }

        days = review_intervals[level]

        next_review = (
            today
            + timedelta(days=days)
        ).isoformat()

    # =====================================================
    # 写入 word_progress
    # =====================================================

    cursor.execute("""
        INSERT OR REPLACE INTO word_progress (
            word_id,
            level,
            last_review,
            next_review,
            correct_count,
            wrong_count,
            learned,
            in_wrong
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (

        word_id,

        level,

        last_review,

        next_review,

        correct_count,

        wrong_count,

        learned,

        in_wrong

    ))

    cursor.execute("""
        INSERT OR REPLACE INTO progress_store (
            word_key,
            word,
            level,
            last_review,
            next_review,
            correct_count,
            wrong_count,
            learned,
            in_wrong
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        normalize_word_key(word_text),
        word_text,
        level,
        last_review,
        next_review,
        correct_count,
        wrong_count,
        learned,
        in_wrong
    ))

    # =====================================================
    # 保存学习日志
    # =====================================================

    cursor.execute("""
        INSERT INTO study_log (
            word_id,
            study_date,
            study_type,
            result
        )
        VALUES (?, ?, ?, ?)
    """, (

        word_id,

        today.isoformat(),

        study_type,

        result

    ))
    # =====================================================
    # 学习次数 +1
    # =====================================================

    cursor.execute("""
        SELECT value
        FROM app_meta
        WHERE key = 'total_studied'
    """)

    row = cursor.fetchone()

    total_studied = 0

    if row:

        try:

            total_studied = int(
                row["value"]
            )

        except (
            ValueError,
            TypeError
        ):

            total_studied = 0

    total_studied += 1

    cursor.execute("""
        INSERT OR REPLACE INTO app_meta (
            key,
            value
        )
        VALUES ('total_studied', ?)
    """, (
        str(total_studied),
    ))

    conn.commit()

    # =====================================================
    # 返回最新数据
    # =====================================================

    cursor.execute("""
        SELECT
            word_id,
            level,
            last_review,
            next_review,
            correct_count,
            wrong_count
        FROM word_progress
        WHERE word_id = ?
    """, (
        word_id,
    ))

    progress_row = cursor.fetchone()

    conn.close()

    return jsonify({

        "success": True,

        "progress": {

            "word_id":
                progress_row["word_id"],

            "level":
                progress_row["level"],

            "last_review":
                progress_row["last_review"],

            "next_review":
                progress_row["next_review"],

            "correct_count":
                progress_row["correct_count"],

            "wrong_count":
                progress_row["wrong_count"]

        }

    })


# =========================================================
# 数据库状态检查
# =========================================================

@app.route("/api/db-status")
def db_status():

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM words
    """)

    word_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM word_progress
    """)

    progress_count = cursor.fetchone()[0]

    conn.close()

    return jsonify({

        "success": True,

        "word_count": word_count,

        "progress_count": progress_count

    })


# =========================================================
# 查看数据库学习记录
# =========================================================

@app.route("/api/db-progress")
def db_progress():

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            word_id,
            level,
            last_review,
            next_review,
            correct_count,
            wrong_count,
            learned,
            in_wrong
        FROM word_progress
        ORDER BY word_id
    """)

    rows = cursor.fetchall()

    conn.close()

    progress = [
        dict(row)
        for row in rows
    ]

    return jsonify({

        "success": True,

        "progress": progress

    })
# =========================================================
# 重置所有学习数据
#
# 只删除学习记录，不删除单词
# =========================================================

@app.route("/api/reset-progress", methods=["POST"])
def reset_progress():

    conn = get_db()

    cursor = conn.cursor()

    # 删除所有学习状态
    cursor.execute("""
        DELETE FROM word_progress
    """)
    cursor.execute("""
        DELETE FROM progress_store
    """)
    cursor.execute("""
        DELETE FROM study_log
    """)
    # 总学习次数归零
    cursor.execute("""
        INSERT OR REPLACE INTO app_meta (
            key,
            value
        )
        VALUES ('total_studied', '0')
    """)

    conn.commit()

    conn.close()

    return jsonify({

        "success": True,

        "message": "学习数据已全部重置"

    })

# =========================================================
# 开发测试：让指定单词立即到期
# =========================================================

@app.route(
    "/api/test-make-due/<int:word_id>",
    methods=["POST"]
)
def test_make_due(word_id):

    today = date.today().isoformat()

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM words
        WHERE id = ?
    """, (
        word_id,
    ))

    if cursor.fetchone() is None:

        conn.close()

        return jsonify({

            "success": False,

            "message": "找不到这个单词"

        }), 404

    # 确保存在学习记录
    cursor.execute("""
        INSERT OR IGNORE INTO word_progress (
            word_id,
            level,
            last_review,
            next_review,
            correct_count,
            wrong_count,
            learned,
            in_wrong
        )
        VALUES (?, 0, ?, ?, 0, 0, 1, 0)
    """, (
        word_id,
        today,
        today
    ))

    # 如果已经有记录，直接把下次复习改成今天
    cursor.execute("""
        UPDATE word_progress

        SET next_review = ?

        WHERE word_id = ?
    """, (
        today,
        word_id
    ))

    conn.commit()

    conn.close()

    return jsonify({

        "success": True,

        "word_id": word_id,

        "next_review": today,

        "message":
            "该单词已经被设置为今天到期"

    })
# =========================================================
# 启动
# =========================================================

if __name__ == "__main__":

    # 创建数据库
    init_database()

    # 同步默认词书并导入当前词书
    sync_system_wordbook()
    import_ecdict_words()

    # 启动 Flask
    app.run(debug=True)