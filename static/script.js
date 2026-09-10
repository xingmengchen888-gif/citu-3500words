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
// 显示单词
// ========================================

function showStudyPage() {

    const word = words[currentIndex];

    if (!word) {

        alert("没有更多单词了");

        return;
    }

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

            <div class="study-meaning">
                ${word.meaning || "暂无释义"}
            </div>


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
                个新单词。
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

    }

}


// ========================================
// 左侧导航：页面切换
// ========================================

function navigatePage(page) {


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

        showWrongWords();

        return;
    }


    // ------------------------------
    // 统计
    // ------------------------------

    if (page === "stats") {

        setActiveNav("stats");

        showStatistics();

        return;
    }


    // ------------------------------
    // 词库
    // ------------------------------

    if (page === "words") {

        setActiveNav("words");

        toast("词库功能下一步开放");

        return;
    }


    // ------------------------------
    // 生词本
    // ------------------------------

    if (page === "new") {

        setActiveNav("new");

        toast("生词本功能下一步开放");

        return;
    }


    // ------------------------------
    // 设置
    // ------------------------------

    if (page === "settings") {

        setActiveNav("settings");

        toast("设置功能下一步开放");

        return;
    }

}