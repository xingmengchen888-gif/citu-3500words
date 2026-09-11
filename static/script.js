// ========================================
// 单词学习系统
// ========================================

let words = [];
let currentIndex = 0;
let currentStudyType = "新词";

// ========================================
// 开始学习
// ========================================

async function startStudy(type) {

    try {

        let response;
        let data;

        // ==========================
        // 新词学习
        // ==========================

        if (type === "新词") {

            response =
                await fetch("/api/today-words");

            data =
                await response.json();

        }

        // ==========================
        // 开始复习
        // ==========================

        else if (type === "复习") {

            response =
                await fetch("/api/review-words");

            data =
                await response.json();

        }

        else {

            alert("未知的学习类型");

            return;
        }


        // ==========================
        // 没有单词
        // ==========================

        if (!data.words || data.words.length === 0) {

            alert(
                type === "复习"
                    ? "今天没有需要复习的单词 🎉"
                    : "今天没有新的单词了 🎉"
            );

            return;
        }


        // ==========================
        // 保存当前学习列表
        // ==========================

        words = data.words;
        currentStudyType = type;
        currentIndex = 0;


        // ==========================
        // 进入学习页面
        // ==========================

        showStudyPage();


    } catch (error) {

        console.error(error);

        alert(
            type === "复习"
                ? "获取复习单词失败，请检查后端是否正在运行"
                : "获取今日学习单词失败，请检查后端是否正在运行"
        );

    }
}


// ========================================
// 学习界面：释义精简 / 折叠
// ========================================

function splitStudyMeanings(value) {
    const text = String(value || "").trim();
    if (!text) return [];

    return text
        .split(/[；;]\s*|(?<=\S)[，,]\s*(?=[^，,；;]{1,18}(?:[；;,]|$))/)
        .map(item => item.trim())
        .filter(Boolean);
}

function renderStudyMeaning(value) {
    const meanings = splitStudyMeanings(value);

    if (!meanings.length) {
        return `<div class="study-meaning">暂无释义</div>`;
    }

    const visible = meanings.slice(0, 2);
    const hidden = meanings.slice(2);

    const visibleHTML = visible
        .map(item => `<div class="study-meaning-item">${escapeHTML(item)}</div>`)
        .join("");

    if (!hidden.length) {
        return `<div class="study-meaning study-meaning-simple">${visibleHTML}</div>`;
    }

    const hiddenHTML = hidden
        .map(item => `<div class="study-meaning-popover-item">${escapeHTML(item)}</div>`)
        .join("");

    return `
        <div class="study-meaning-wrap">
            <div class="study-meaning study-meaning-simple">
                ${visibleHTML}
            </div>

            <div class="study-meaning-more">
                <button
                    type="button"
                    class="study-meaning-more-btn"
                    onclick="toggleStudyMeanings(event)"
                    aria-expanded="false"
                >
                    查看其他 ${hidden.length} 个释义
                    <span>⌄</span>
                </button>

                <div class="study-meaning-popover" hidden>
                    <div class="study-meaning-popover-title">其他释义</div>
                    ${hiddenHTML}
                </div>
            </div>
        </div>
    `;
}

function toggleStudyMeanings(event) {
    event.stopPropagation();

    const button = event.currentTarget;
    const popover = button.parentElement.querySelector(".study-meaning-popover");
    const isOpen = !popover.hidden;

    document.querySelectorAll(".study-meaning-popover").forEach(item => {
        item.hidden = true;
    });

    document.querySelectorAll(".study-meaning-more-btn").forEach(item => {
        item.setAttribute("aria-expanded", "false");
    });

    if (!isOpen) {
        popover.hidden = false;
        button.setAttribute("aria-expanded", "true");
    }
}

document.addEventListener("click", function(event) {
    if (!event.target.closest(".study-meaning-more")) {
        document.querySelectorAll(".study-meaning-popover").forEach(item => {
            item.hidden = true;
        });
        document.querySelectorAll(".study-meaning-more-btn").forEach(item => {
            item.setAttribute("aria-expanded", "false");
        });
    }
});

// ========================================
// 显示单词
// ========================================

function showStudyPage() {

    const word = words[currentIndex];

    if (!word) {

        alert("没有更多单词了");

        return;
    }

    const meaningHTML = renderStudyMeaning(word.meaning);

    // 有音标才显示音标区域
    const phoneticHTML = word.phonetic
        ? `
            <div class="study-phonetic">
                ${word.phonetic}
            </div>
          `
        : "";

    // 有例句才显示例句区域
    const exampleHTML =
        word.example || word.example_cn
        ? `
            <div class="study-example">

                ${
                    word.example
                        ? `<div>${word.example}</div>`
                        : ""
                }

                ${
                    word.example_cn
                        ? `
                            <div class="study-example-cn">
                                ${word.example_cn}
                            </div>
                          `
                        : ""
                }

            </div>
          `
        : "";

    document.querySelector(".main").innerHTML = `

        <div class="card study-card">

            <!-- 学习进度 -->
            <div class="study-progress">
                第 ${currentIndex + 1} / ${words.length} 词
            </div>


            <!-- 单词 -->
            <div class="study-word">
                ${word.word}
            </div>
            <div class="study-pos">
                ${word.pos || ""}
            </div>
            <button
                class="speak-btn"
                onclick="speakWord('${word.word.replace(/'/g, "\\'")}')"
                title="播放发音"
            >
                🔊 发音
            </button>
            <!-- 音标：有才显示 -->
            ${phoneticHTML}


            <!-- 中文释义 -->
            <div class="study-meaning-label">
                词义
            </div>

            ${meaningHTML}


            <!-- 例句：有才显示 -->
            ${exampleHTML}


            <!-- 按钮 -->
            <div class="study-buttons">

                <button
                    class="study-btn unknown"
                    onclick="recordAndNext('unknown')"
                >
                    不认识
                </button>

                <button
                    class="study-btn known"
                    onclick="recordAndNext('known')"
                >
                    认识
                </button>

            </div>

        </div>

    `;
}


// ========================================
// 保存学习结果，然后进入下一个单词
// ========================================

async function recordAndNext(result) {

    const word = words[currentIndex];

    try {

        const response = await fetch("/api/record", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({

                word_id: word.id,

                result: result,

                study_type: currentStudyType

            })

        });


        const data = await response.json();


        if (!data.success) {

            alert("保存学习记录失败");

            return;
        }


        console.log("学习记录保存成功：", data);


        // 进入下一个单词

        currentIndex++;


        if (currentIndex >= words.length) {

            showCompletePage();

            return;
        }


        showStudyPage();


    } catch (error) {

        console.error(error);

        alert("无法连接服务器");

    }

}


// ========================================
// 学习完成
// ========================================

function showCompletePage() {

    document.querySelector(".main").innerHTML = `

        <div class="card study-card">

            <div class="complete-icon">
                🎉
            </div>

            <h2>
                今日学习完成！
            </h2>

            <p>
                你今天完成了
                <strong>${words.length}</strong>
                个${currentStudyType === "复习" ? "复习单词" : "新单词"}。
            </p>

            <p style="color:var(--muted); margin-top:8px;">
                继续保持，明天再来学习吧！
            </p>

            <button
                class="primary"
                onclick="location.reload()"
            >
                返回首页
            </button>

        </div>

    `;

}
// ========================================
// 错词本
// ========================================

async function showWrongWords() {

    try {

        const response = await fetch("/api/wrong-words");

        const wrongWords = await response.json();

        showWrongWordsPage(wrongWords);

    } catch (error) {

        console.error(error);

        alert("获取错词失败，请检查后端是否正在运行");

    }

}


// ========================================
// 显示错词本页面
// ========================================

function showWrongWordsPage(wrongWords) {

    let content = "";

    if (wrongWords.length === 0) {

        content = `

            <div class="empty-wrong">

                <div class="empty-icon">
                    🎉
                </div>

                <h2>太棒了！</h2>

                <p>
                    目前没有需要复习的错词
                </p>

            </div>

        `;

    } else {

        content = `

            <div class="wrong-list">

        `;

        wrongWords.forEach(word => {

            content += `

                <div class="wrong-word-item">

                    <div>

                        <div class="wrong-word">
                            ${word.word}
                        </div>

                        <div class="wrong-phonetic">
                            ${word.phonetic || ""}
                        </div>

                    </div>


                    <div class="wrong-meaning">
                        ${word.meaning || ""}
                    </div>


                    <button
                        class="outline wrong-review-btn"
                        onclick="reviewWrongWord(${word.id})"
                    >
                        开始复习
                    </button>

                </div>

            `;

        });

        content += `</div>`;

    }


    document.querySelector(".main").innerHTML = `

        <div class="card wrong-page">

            <div class="wrong-header">

                <div>

                    <div class="section-title">
                        错词本
                    </div>

                    <div class="wrong-count">
                        共 ${wrongWords.length} 个需要复习
                    </div>

                </div>

            </div>


            ${content}

        </div>

    `;

}


// ========================================
// 复习某一个错词
// ========================================

async function reviewWrongWord(wordId) {

    try {

        const response = await fetch("/api/words");

        const allWords = await response.json();

        const word = allWords.find(
            item => item.id === wordId
        );


        if (!word) {

            alert("找不到这个单词");

            return;

        }


        // 当前只复习这一个词

        currentStudyType = "复习";

        words = [word];

        currentIndex = 0;

        showStudyPage();


    } catch (error) {

        console.error(error);

        alert("获取单词失败");

    }

}
// ========================================
// 加载首页学习统计
// ========================================

async function loadHomeStats() {

    try {

        const response = await fetch("/api/stats");

        const stats = await response.json();


        // 已学习数量
        const learnedCount = document.getElementById("learned-count");

        if (learnedCount) {
            learnedCount.textContent = stats.learned_count;
        }


        // 总词数
        const totalCount = document.getElementById("total-count");

        if (totalCount) {
            totalCount.textContent = stats.total_words;
        }


        // 已学习数量（下面那一行）
        const learnedCount2 = document.getElementById("learned-count-2");

        if (learnedCount2) {
            learnedCount2.textContent = stats.learned_count;
        }


        // 剩余数量
        const remainingCount = document.getElementById("remaining-count");

        if (remainingCount) {
            remainingCount.textContent = stats.remaining_count;
        }


        // 完成度
        const percentage = document.getElementById("progress-percentage");

        if (percentage) {

            percentage.innerHTML = `

                ${stats.percentage}%

                <small>完成度</small>

            `;

        }


        // 进度条
        const progressBar = document.getElementById("progress-bar");

        if (progressBar) {

            progressBar.style.width =
                stats.percentage + "%";

        }
        // 圆环进度
        const ring = document.querySelector(".ring");

        if (ring) {

            ring.style.setProperty(
                "--progress",
                stats.percentage + "%"
            );

        }


    } catch (error) {

        console.error("加载学习统计失败：", error);

    }

}


// ========================================
// 页面加载完成后获取统计
// ========================================

document.addEventListener("DOMContentLoaded", function() {

    loadHomeStats();

});
// 获取今日新学单词数量
async function loadTodayPlan() {

    try {

        // 今日新词
        const newResponse = await fetch("/api/today-words");
        const newData = await newResponse.json();

        const newCountElement =
            document.getElementById("today-new-count");

        if (newCountElement) {

            newCountElement.textContent =
                newData.count;

        }


        // 今日复习
        const reviewResponse =
            await fetch("/api/review-words");

        const reviewData =
            await reviewResponse.json();

        const reviewCountElement =
            document.getElementById("today-review-count");

        if (reviewCountElement) {

            reviewCountElement.textContent =
                reviewData.count;

        }

    } catch (error) {

        console.error(
            "获取今日学习计划失败：",
            error
        );

    }
}
document.addEventListener(
    "DOMContentLoaded",
    function(){

        loadHomeStats();

        loadTodayPlan();

        loadTodayProgress();

        const initialPage = new URLSearchParams(
            window.location.search
        ).get("page");

        if (initialPage && initialPage !== "home") {
            navigatePage(initialPage);
        }

    }
);

// ========================================
// 开发测试：重置所有学习数据
// ========================================

async function resetLearningData() {

    const ok = confirm(
        "确定要把所有学习记录清零吗？"
    );

    if (!ok) {
        return;
    }

    try {

        const response = await fetch(
            "/api/reset-progress",
            {
                method: "POST"
            }
        );

        const data = await response.json();

        if (data.success) {

            alert("学习数据已经全部清零！");

            location.reload();

        } else {

            alert("重置失败");

        }

    } catch (error) {

        console.error(error);

        alert("无法连接服务器");

    }
}

// ========================================
// 开发测试：让某个单词今天到期
// ========================================

async function makeWordDue(wordId) {

    try {

        const response = await fetch(
            `/api/test-make-due/${wordId}`,
            {
                method: "POST"
            }
        );

        const data = await response.json();

        if (data.success) {

            alert(
                `单词 ${wordId} 已设置为今天到期`
            );

        } else {

            alert(data.message);

        }

    } catch (error) {

        console.error(error);

        alert("设置失败");

    }
}
// ========================================
// 单词发音
// ========================================

function speakWord(word) {


    if (!window.speechSynthesis) {

        alert("浏览器不支持语音");

        return;
    }


    // 清除之前播放
    speechSynthesis.cancel();


    let voices =
        speechSynthesis.getVoices();


    // 找英语声音
    let englishVoice =
        voices.find(function(voice){

            return voice.lang.includes("en");

        });


    const utterance =
        new SpeechSynthesisUtterance(word);


    utterance.lang="en-US";


    // 如果找到英语声音，强制使用
    if(englishVoice){

        utterance.voice =
            englishVoice;

    }


    // 速度稍慢，更适合背词
    utterance.rate = 0.75;


    // 音调
    utterance.pitch = 1;


    speechSynthesis.speak(
        utterance
    );

}
// ========================================
// 学习页面键盘快捷键
// ← 不认识
// → 认识
// ========================================

document.addEventListener("keydown", function(event) {

    // 如果当前不是学习页面，不处理
    if (!words || !words.length) {
        return;
    }

    // 输入框里打字时不要触发
    const tag = document.activeElement.tagName;

    if (
        tag === "INPUT" ||
        tag === "TEXTAREA"
    ) {
        return;
    }


    // 左箭头：不认识
    if (event.key === "ArrowLeft") {

        recordAndNext("unknown");

    }


    // 右箭头：认识
    else if (event.key === "ArrowRight") {

        recordAndNext("known");

    }


    // 空格：播放发音
    else if (event.key === " ") {

        event.preventDefault();

        const word = words[currentIndex];

        if (word) {

            speakWord(word.word);

        }

    }

});
// ========================================
// 获取今日学习进度
// ========================================

async function loadTodayProgress(){

    try{

        const response =
            await fetch("/api/today-progress");

        const data =
            await response.json();


        document.getElementById(
            "today-new-completed"
        ).textContent =
            data.new_completed;


        document.getElementById(
            "today-new-total"
        ).textContent =
            data.new_total;


        document.getElementById(
            "today-review-completed"
        ).textContent =
            data.review_completed;


        document.getElementById(
            "today-review-total"
        ).textContent =
            data.review_total;


        document.getElementById(
            "today-total-completed"
        ).textContent =
            data.total_completed;


        document.getElementById(
            "today-total-target"
        ).textContent =
            data.total_target;


        document.getElementById(
            "today-progress-percentage"
        ).textContent =
            data.percentage + "%";


        document.getElementById(
            "today-progress-fill"
        ).style.width =
            data.percentage + "%";


    }catch(error){

        console.error(
            "加载今日学习进度失败：",
            error
        );

    }

}
async function showStatistics(){


    const response =
        await fetch("/api/statistics");


    const data =
        await response.json();



    document.querySelector(".main").innerHTML = `


    <div class="card">


        <h2>
            学习统计
        </h2>


        <div class="stats-grid">


            <div class="stats-box">

                <div>
                    总词汇量
                </div>

                <strong>
                    ${data.total_words}
                </strong>

            </div>



            <div class="stats-box">

                <div>
                    已学习
                </div>

                <strong>
                    ${data.learned_words}
                </strong>

            </div>



            <div class="stats-box">

                <div>
                    已掌握
                </div>

                <strong>
                    ${data.mastered_words}
                </strong>

            </div>



            <div class="stats-box">

                <div>
                    错词
                </div>

                <strong>
                    ${data.wrong_words}
                </strong>

            </div>



        </div>



        <div class="stat-big">


            累计学习

            <span>
                ${data.total_study}
            </span>

            次


        </div>



        <div class="stat-big">


            今日学习

            <span>
                ${data.today_study}
            </span>

            次


        </div>


    </div>


    `;

}

// ========================================
// 左侧导航：设置当前高亮
// ========================================

function setActiveNav(page) {

    const buttons =
        document.querySelectorAll(".nav button");

    buttons.forEach(function(button) {

        button.classList.remove("active");

    });

    const activeButton =
        document.querySelector(
            `.nav button[data-page="${page}"]`
        );

    if (activeButton) {

        activeButton.classList.add("active");

        // 点击后让焦点跟随当前功能，尤其是未开放功能。
        activeButton.focus({ preventScroll: true });

    }

}


// ========================================
// 左侧导航：页面切换
// ========================================

function navigatePage(page) {

    closeWordBookModal();

    // ------------------------------
    // 首页
    // ------------------------------

    if (page === "home") {

        setActiveNav("home");

        location.reload();

        return;
    }


    // ------------------------------
    // 学习
    // ------------------------------

    if (page === "study") {

        setActiveNav("study");

        startStudy("新词");

        return;
    }


    // ------------------------------
    // 复习
    // ------------------------------

    if (page === "review") {

        setActiveNav("review");

        startStudy("复习");

        return;
    }


    // ------------------------------
    // 错词本
    // ------------------------------

    if (page === "wrong") {

        setActiveNav("wrong");

        words = [];
        currentIndex = 0;

        showWrongWords();

        return;
    }


    // ------------------------------
    // 统计
    // ------------------------------

    if (page === "stats") {

        setActiveNav("stats");

        words = [];
        currentIndex = 0;

        showStatistics();

        return;
    }


    // ------------------------------
    // 词库
    // ------------------------------

    if (page === "words") {

        setActiveNav("words");

        words = [];
        currentIndex = 0;

        showWordLibrary(1);

        return;
    }


    // ------------------------------
    // 生词本
    // ------------------------------

    if (page === "new") {

        setActiveNav("new");

        words = [];
        currentIndex = 0;

        toast("生词本功能下一步开放");

        return;
    }


    // ------------------------------
    // 设置
    // ------------------------------

    if (page === "settings") {

        setActiveNav("settings");

        words = [];
        currentIndex = 0;

        toast("设置功能下一步开放");

        return;
    }

}

// ========================================
// 词库：搜索、筛选、分页和详情
// ========================================

const libraryState = {
    page: 1,
    query: "",
    status: "all",
    words: [],
    wordbook: null,
    wordbooks: []
};

const wordStatusLabels = {
    new: "未学习",
    learning: "学习中",
    mastered: "已掌握",
    wrong: "错词"
};

function escapeHTML(value) {

    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatWordHTML(value) {

    return escapeHTML(value || "")
        .replace(/\n/g, "<br>");
}

function getMeaningPreview(value) {

    const lines = String(value || "")
        .split("\n")
        .map(line => line.trim())
        .filter(Boolean);

    const preview = lines
        .slice(0, 2)
        .map(line => escapeHTML(line))
        .join("<br>");

    return preview || "暂无释义";
}

function getWordStatusLabel(status) {

    return wordStatusLabels[status] || status || "未学习";
}

function renderLibraryPagination(page, pages) {

    if (pages <= 1) {
        return "";
    }

    return `
        <div class="library-pagination">

            <button
                class="outline"
                ${page <= 1 ? "disabled" : ""}
                onclick="showWordLibrary(${page - 1})"
            >
                上一页
            </button>

            <span>
                第 ${page} / ${pages} 页
            </span>

            <button
                class="outline"
                ${page >= pages ? "disabled" : ""}
                onclick="showWordLibrary(${page + 1})"
            >
                下一页
            </button>

        </div>
    `;
}

function renderWordLibrary(data) {

    libraryState.words = data.words || [];
    libraryState.wordbook = data.wordbook || null;
    libraryState.wordbooks = data.wordbooks || [];

    const listHTML = libraryState.words.length
        ? libraryState.words.map(word => {

            const status = word.progress_status || "new";

            const phonetic = word.phonetic
                ? `<span class="library-phonetic">${escapeHTML(word.phonetic)}</span>`
                : "";

            const pos = word.pos
                ? `<span class="library-pos">${escapeHTML(word.pos)}</span>`
                : "";

            const tags = word.tag
                ? `<div class="library-detail-line"><b>标签</b>${escapeHTML(word.tag)}</div>`
                : "";

            const exchange = word.exchange
                ? `<div class="library-detail-line"><b>词形</b>${escapeHTML(word.exchange)}</div>`
                : "";

            const definition = word.definition
                ? `<div class="library-detail-section"><b>英文释义</b><div>${formatWordHTML(word.definition)}</div></div>`
                : "";

            return `
                <article class="library-word-item status-${escapeHTML(status)}">

                    <div class="library-word-main">

                        <div class="library-word-heading">
                            <strong>${escapeHTML(word.word)}</strong>
                            ${phonetic}
                            ${pos}
                        </div>

                        <div class="library-meaning">
                            ${getMeaningPreview(word.meaning)}
                        </div>

                    </div>

                    <div class="library-word-side">

                        <span class="library-status status-${escapeHTML(status)}">
                            ${escapeHTML(getWordStatusLabel(status))}
                        </span>

                        <button
                            class="outline library-icon-btn"
                            onclick="speakLibraryWord(${word.id})"
                            title="播放发音"
                        >
                            🔊
                        </button>

                        <button
                            class="outline library-icon-btn"
                            onclick="toggleWordDetail(${word.id})"
                        >
                            详情
                        </button>

                    </div>

                </article>

                <div
                    class="library-detail"
                    id="library-detail-${word.id}"
                    hidden
                >

                    <div class="library-detail-section">
                        <b>中文释义</b>
                        <div>${formatWordHTML(word.translation || word.meaning)}</div>
                    </div>

                    ${definition}

                    <div class="library-detail-meta">

                        ${tags}
                        ${exchange}

                        <div class="library-detail-line">
                            <b>学习状态</b>
                            等级 ${word.level || 0}
                            · 认识 ${word.correct_count || 0}
                            · 错误 ${word.wrong_count || 0}
                            ${word.next_review ? ` · 下次复习 ${escapeHTML(word.next_review)}` : ""}
                        </div>

                    </div>

                </div>
            `;

        }).join("")
        : `
            <div class="library-empty">
                <strong>没有找到匹配的单词</strong>
                <p>可以换个关键词或切换筛选条件。</p>
            </div>
        `;

    const wordbookOptions = libraryState.wordbooks.map(book => `
        <option
            value="${book.id}"
            ${libraryState.wordbook && libraryState.wordbook.id === book.id ? "selected" : ""}
        >
            ${escapeHTML(book.name)}（${book.word_count} 词）
        </option>
    `).join("");

    const statusOptions = [
        ["all", "全部"],
        ["new", "未学习"],
        ["learning", "学习中"],
        ["mastered", "已掌握"],
        ["wrong", "错词"]
    ].map(([value, label]) => `
        <option
            value="${value}"
            ${libraryState.status === value ? "selected" : ""}
        >
            ${label}
        </option>
    `).join("");

    const activeWordBookName = libraryState.wordbook
        ? escapeHTML(libraryState.wordbook.name)
        : "未选择词书";

    document.querySelector(".main").innerHTML = `

        <div class="card library-page">

            <div class="library-header">

                <div>
                    <div class="section-title">词库</div>
                    <div class="library-count">
                        筛选结果 ${data.total} 个词
                        <span>·</span>
                        当前 ${activeWordBookName}
                        <span>·</span>
                        ${libraryState.wordbook ? libraryState.wordbook.word_count : 0} 词
                    </div>
                </div>

                <div class="library-source">
                    ECDICT · 自定义词书
                </div>

            </div>

            <div class="library-toolbar">

                <div class="library-book-row">

                    <span class="library-toolbar-label">
                        当前词书
                    </span>

                    <select
                        id="library-wordbook-select"
                        class="outline"
                        onchange="switchWordBook(this.value)"
                    >
                        ${wordbookOptions}
                    </select>

                    <button
                        class="outline library-toolbar-btn"
                        onclick="openWordBookModal()"
                    >
                        新建词书
                    </button>

                    <button
                        class="outline library-toolbar-btn"
                        onclick="editCurrentWordBook()"
                    >
                        编辑当前
                    </button>

                </div>

                <div class="library-filter-row">

                    <div class="library-search">
                        <input
                            id="library-search-input"
                            type="search"
                            value="${escapeHTML(libraryState.query)}"
                            placeholder="搜索单词、中文释义或标签"
                        >

                        <button
                            class="primary"
                            onclick="searchWordLibrary()"
                        >
                            搜索
                        </button>
                    </div>

                    <select
                        id="library-status-select"
                        class="outline"
                        onchange="searchWordLibrary()"
                    >
                        ${statusOptions}
                    </select>

                </div>

            </div>

            <div class="library-list">
                ${listHTML}
            </div>

            ${renderLibraryPagination(data.page, data.pages)}

        </div>
    `;

    const searchInput = document.getElementById(
        "library-search-input"
    );

    if (searchInput) {

        searchInput.addEventListener("keydown", function(event) {

            if (event.key === "Enter") {

                searchWordLibrary();

            }

        });

    }
}

async function showWordLibrary(page = 1) {

    setActiveNav("words");

    try {

        const params = new URLSearchParams({
            page: String(page),
            per_page: "40",
            status: libraryState.status
        });

        if (libraryState.query) {

            params.set("q", libraryState.query);

        }

        const response = await fetch(
            `/api/library?${params.toString()}`
        );

        const data = await response.json();

        if (!data.success) {

            throw new Error(data.message || "加载词库失败");

        }

        libraryState.page = data.page;

        renderWordLibrary(data);

    } catch (error) {

        console.error(error);

        alert("加载词库失败，请检查后端是否正在运行");

    }
}

function searchWordLibrary() {

    const input = document.getElementById(
        "library-search-input"
    );

    const select = document.getElementById(
        "library-status-select"
    );

    libraryState.query = input
        ? input.value.trim()
        : "";

    libraryState.status = select
        ? select.value
        : "all";

    showWordLibrary(1);
}

function speakLibraryWord(wordId) {

    const word = libraryState.words.find(
        item => item.id === wordId
    );

    if (word) {

        speakWord(word.word);

    }
}

function toggleWordDetail(wordId) {

    const detail = document.getElementById(
        `library-detail-${wordId}`
    );

    if (detail) {

        detail.hidden = !detail.hidden;

    }
}

// ========================================
// 自定义词书
// ========================================

let editingWordBookId = null;

async function switchWordBook(bookId) {

    bookId = Number(bookId);

    if (
        !bookId ||
        (libraryState.wordbook && libraryState.wordbook.id === bookId)
    ) {
        return;
    }

    const select = document.getElementById(
        "library-wordbook-select"
    );

    if (select) {
        select.disabled = true;
    }

    toast("正在切换词书...");

    try {

        const response = await fetch(
            `/api/wordbooks/${bookId}/activate`,
            { method: "POST" }
        );

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.message || "切换词书失败");
        }

        libraryState.query = "";
        libraryState.status = "all";

        await showWordLibrary(1);

    } catch (error) {

        console.error(error);
        alert(error.message || "切换词书失败");

        if (select) {
            select.disabled = false;

            if (libraryState.wordbook) {
                select.value = String(libraryState.wordbook.id);
            }
        }
    }
}

function editCurrentWordBook() {

    if (!libraryState.wordbook) {
        return;
    }

    if (libraryState.wordbook.is_system) {
        toast("默认词书请直接编辑 03_data/wordlist.txt");
        return;
    }

    openWordBookModal(libraryState.wordbook.id);
}

async function openWordBookModal(bookId = null) {

    closeWordBookModal();

    editingWordBookId = bookId ? Number(bookId) : null;

    let name = "";
    let words = "";
    let wordCount = 0;

    if (editingWordBookId) {

        try {

            const response = await fetch(
                `/api/wordbooks/${editingWordBookId}`
            );

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.message || "加载词书失败");
            }

            name = data.wordbook.name || "";
            words = data.wordbook.words || "";
            wordCount = data.wordbook.word_count || 0;

        } catch (error) {

            console.error(error);
            alert(error.message || "加载词书失败");
            return;
        }
    }

    const title = editingWordBookId
        ? "编辑自定义词书"
        : "新建自定义词书";

    const deleteButton = editingWordBookId
        ? `
            <button
                class="outline danger"
                onclick="deleteCurrentWordBook()"
            >
                删除词书
            </button>
        `
        : "";

    document.body.insertAdjacentHTML(
        "beforeend",
        `
            <div
                class="wordbook-modal-backdrop"
                onclick="handleWordBookBackdrop(event)"
            >

                <div class="wordbook-modal">

                    <div class="wordbook-modal-header">

                        <div>
                            <h2>${title}</h2>
                            <p>一行一个单词，支持直接粘贴或导入 txt 文件。</p>
                        </div>

                        <button
                            class="wordbook-modal-close"
                            onclick="closeWordBookModal()"
                        >
                            ×
                        </button>

                    </div>

                    <label class="wordbook-field">
                        <span>词书名称</span>
                        <input
                            id="wordbook-name-input"
                            type="text"
                            maxlength="40"
                            value="${escapeHTML(name)}"
                            placeholder="例如：雅思核心词"
                        >
                    </label>

                    <label class="wordbook-field">
                        <span>
                            单词列表
                            ${wordCount ? `<small>当前 ${wordCount} 词</small>` : ""}
                        </span>

                        <textarea
                            id="wordbook-words-input"
                            placeholder="abandon&#10;ability&#10;able"
                        >${escapeHTML(words)}</textarea>
                    </label>

                    <label class="wordbook-file">
                        <input
                            id="wordbook-file-input"
                            type="file"
                            accept=".txt,text/plain"
                            onchange="loadWordBookFile(event)"
                        >
                        <span>选择 txt 文件</span>
                    </label>

                    <div class="wordbook-modal-actions">

                        <div>${deleteButton}</div>

                        <div class="wordbook-modal-primary-actions">

                            <button
                                class="outline"
                                onclick="closeWordBookModal()"
                            >
                                取消
                            </button>

                            <button
                                class="primary"
                                id="wordbook-save-button"
                                onclick="saveWordBook()"
                            >
                                保存并启用
                            </button>

                        </div>

                    </div>

                </div>

            </div>
        `
    );

    document.body.classList.add("modal-open");

    const nameInput = document.getElementById(
        "wordbook-name-input"
    );

    if (nameInput) {
        nameInput.focus();
    }
}

function closeWordBookModal() {

    const modal = document.querySelector(
        ".wordbook-modal-backdrop"
    );

    if (modal) {
        modal.remove();
    }

    document.body.classList.remove("modal-open");
    editingWordBookId = null;
}

function handleWordBookBackdrop(event) {

    if (event.target.classList.contains("wordbook-modal-backdrop")) {
        closeWordBookModal();
    }
}

function loadWordBookFile(event) {

    const file = event.target.files
        ? event.target.files[0]
        : null;

    if (!file) {
        return;
    }

    const reader = new FileReader();

    reader.onload = function() {

        const textarea = document.getElementById(
            "wordbook-words-input"
        );

        if (textarea) {
            textarea.value = String(reader.result || "");
        }
    };

    reader.onerror = function() {
        alert("读取 txt 文件失败");
    };

    reader.readAsText(file, "UTF-8");
}

async function saveWordBook() {

    const nameInput = document.getElementById(
        "wordbook-name-input"
    );

    const wordsInput = document.getElementById(
        "wordbook-words-input"
    );

    const saveButton = document.getElementById(
        "wordbook-save-button"
    );

    const name = nameInput
        ? nameInput.value.trim()
        : "";

    const words = wordsInput
        ? wordsInput.value
        : "";

    if (!name) {
        alert("请输入词书名称");
        return;
    }

    if (!words.trim()) {
        alert("词书至少需要一个单词");
        return;
    }

    if (saveButton) {
        saveButton.disabled = true;
        saveButton.textContent = "正在保存...";
    }

    const url = editingWordBookId
        ? `/api/wordbooks/${editingWordBookId}`
        : "/api/wordbooks";

    const method = editingWordBookId
        ? "PUT"
        : "POST";

    try {

        const response = await fetch(url, {

            method: method,

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                name: name,
                words: words
            })

        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.message || "保存词书失败");
        }

        closeWordBookModal();

        libraryState.query = "";
        libraryState.status = "all";

        toast(data.message || "词书已保存");

        await showWordLibrary(1);

    } catch (error) {

        console.error(error);
        alert(error.message || "保存词书失败");

        if (saveButton) {
            saveButton.disabled = false;
            saveButton.textContent = "保存并启用";
        }
    }
}

async function deleteCurrentWordBook() {

    if (!editingWordBookId) {
        return;
    }

    const confirmed = confirm(
        "确定删除这个词书吗？词书本身会删除，单词的全局学习记录会保留。"
    );

    if (!confirmed) {
        return;
    }

    try {

        const response = await fetch(
            `/api/wordbooks/${editingWordBookId}`,
            { method: "DELETE" }
        );

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.message || "删除词书失败");
        }

        closeWordBookModal();

        libraryState.query = "";
        libraryState.status = "all";

        toast(data.message || "词书已删除");

        await showWordLibrary(1);

    } catch (error) {

        console.error(error);
        alert(error.message || "删除词书失败");
    }
}
