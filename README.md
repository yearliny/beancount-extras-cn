# Beancount Extras CN

beancount-extras-cn 项目的目标是实现中国常用环境下的 Beancount 插件。目前实现的有：

- 微信账单导入

## Get Start

### 1. 安装此插件包

```bash
pip install https://github.com/yearliny/beancount-extras-cn.git
```

### 2. 在 Beancount 账本目录下，新增配置文件

示例配置如下：

```python
from beancount_extras_cn.importers import WeChatPayImporter

account_mapping = {
    "招商银行(1234)": "Assets:Bank:CMB",
    "零钱": "Assets:TPP:Wechat",
}

CONFIG = [
    WeChatPayImporter(account="Assets:TPP:Wechat", account_mapping=account_mapping),
]
```

### 3. 获取微信账单，并执行 bean-extract 命令

```bash
bean-extract -e wechat-pay.bean importer.py "C:\Users\username\Download\微信支付账单(20220720-20220920).csv" > tmp.bean
```

执行后会生成 temp.bean 文件，调整一下内容即可合并到已有账单中。
