# 数据文件说明

- `wordlist.txt`：自定义学习词表，一行一个单词，顺序就是学习顺序。
- `ecdict.csv`：ECDICT 词典数据，来源为 <https://github.com/skywind3000/ECDICT>。
- `ECDICT_LICENSE`：ECDICT 项目许可证。
- `vocabulary.db`：程序根据前两个文件自动生成的 SQLite 数据库，已在 `.gitignore` 中忽略。

修改 `wordlist.txt` 后重新启动 Flask，程序会自动扫描 `ecdict.csv`，重新导入词表并保留能够匹配到的单词学习进度。

你也可以在网页的“词库”页面新建、编辑、导入和切换自定义词书。自定义词书保存在 `vocabulary.db` 中；当前选中的词书会同时用于学习、复习和词库；切换词书不会删除其他词书中单词的学习进度。
