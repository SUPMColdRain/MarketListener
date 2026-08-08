# 产业链图谱测试夹具（FULL-701/702）

- `html/supply-chain.html`：公司-产品-行业表格，供 HTML 导入定位测试。
- `excel/supply-chain.xlsx`：公司/核心产品/原材料表格，供 Excel 单元格定位测试。
- `pdf/supply-chain.pdf`：ASCII 文本 PDF，供页码+行号定位测试。
- `announcement/2026-08-01-moutai.txt`：公告文本，供行号+偏移定位测试。

二进制样本由 `make_fixtures.py` 生成；该脚本同时被测试参考，修改样本内容后
应重跑脚本并提交新的二进制文件。
