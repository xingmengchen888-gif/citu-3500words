from flask import Flask, render_template, jsonify, request
import json
import sqlite3
from pathlib import Path
from datetime import date, timedelta

app = Flask(__name__)


# =========================================================
# 路径
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "03_data"

WORDS_FILE = DATA_DIR / "words.json"
PROGRESS_FILE = DATA_DIR / "progress.json"
DB_FILE = DATA_DIR / "vocabulary.db"


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
            level TEXT
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

    conn.commit()

    conn.close()


# =========================================================
# JSON → SQLite 第一次迁移
#
# 只执行一次。
# 第一次运行时，以当前 JSON 数据为准。
# 以后正式使用 SQLite。
# =========================================================

def migrate_json_to_database():

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT value
        FROM app_meta
        WHERE key = 'json_migration_done'
    """)

    row = cursor.fetchone()

    # 已经迁移过，就不再重复迁移
    if row and row["value"] == "1":

        conn.close()

        return

    # -----------------------------------------------------
    # 读取 words.json
    # -----------------------------------------------------

    if WORDS_FILE.exists():

        with open(
            WORDS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            words = json.load(f)

    else:

        words = []

    # -----------------------------------------------------
    # 读取 progress.json
    # -----------------------------------------------------

    if PROGRESS_FILE.exists():

        with open(
            PROGRESS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            progress = json.load(f)

    else:

        progress = {
            "learned_ids": [],
            "wrong_ids": [],
            "total_studied": 0,
            "word_progress": {}
        }

    learned_ids = set(
        progress.get("learned_ids", [])
    )

    wrong_ids = set(
        progress.get("wrong_ids", [])
    )

    word_progress = progress.get(
        "word_progress",
        {}
    )

    # -----------------------------------------------------
    # 清理旧数据库中的数据
    #
    # 因为这是第一次迁移，
    # 当前 JSON 才是最新数据。
    # -----------------------------------------------------

    cursor.execute("""
        DELETE FROM word_progress
    """)

    cursor.execute("""
        DELETE FROM words
    """)

    # -----------------------------------------------------
    # 导入单词
    # -----------------------------------------------------

    for word in words:

        cursor.execute("""
            INSERT OR REPLACE INTO words (
                id,
                word,
                pos,
                phonetic,
                meaning,
                example,
                example_cn,
                level
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            word.get("id"),
            word.get("word"),
            word.get("pos"),
            word.get("phonetic"),
            word.get("meaning"),
            word.get("example"),
            word.get("example_cn"),
            word.get("level")
        ))

    # -----------------------------------------------------
    # 导入学习记录
    # -----------------------------------------------------

    all_word_ids = set()

    all_word_ids.update(learned_ids)
    all_word_ids.update(wrong_ids)

    for word_id in word_progress.keys():

        try:

            all_word_ids.add(
                int(word_id)
            )

        except (ValueError, TypeError):

            continue

    for word_id in all_word_ids:

        key = str(word_id)

        info = word_progress.get(
            key,
            {}
        )

        learned = 1 if word_id in learned_ids else 0

        in_wrong = 1 if word_id in wrong_ids else 0

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

            int(word_id),

            info.get(
                "level",
                0
            ),

            info.get(
                "last_review"
            ),

            info.get(
                "next_review"
            ),

            info.get(
                "correct_count",
                0
            ),

            max(
                info.get(
                    "wrong_count",
                    0
                ),
                1 if in_wrong else 0
            ),

            learned,

            in_wrong

        ))

    # -----------------------------------------------------
    # 保存总学习次数
    # -----------------------------------------------------

    total_studied = progress.get(
        "total_studied",
        0
    )

    cursor.execute("""
        INSERT OR REPLACE INTO app_meta (
            key,
            value
        )
        VALUES ('total_studied', ?)
    """, (
        str(total_studied),
    ))

    # -----------------------------------------------------
    # 标记迁移完成
    # -----------------------------------------------------

    cursor.execute("""
        INSERT OR REPLACE INTO app_meta (
            key,
            value
        )
        VALUES ('json_migration_done', '1')
    """)

    conn.commit()

    conn.close()


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

            "message":
                "找不到这个单词"

        }), 404

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

    # 第一次启动时：
    # 把当前 JSON 数据完整迁移进 SQLite
    migrate_json_to_database()

    # 启动 Flask
    app.run(debug=True)