import csv
import datetime
import re
from dataclasses import dataclass
from datetime import datetime
from os import path
from typing import Any
from typing import Dict

from beancount.core import data, flags
from beancount.core.amount import Amount
from beancount.core.number import D
from beancount.ingest import importer
from dateutil import parser


@dataclass
class AlipayBillInfo:
    # 交易类型 [支出|收入|其他]
    trade_type: str
    # 交易时间
    trade_time: datetime
    # 交易对方
    payee: str
    # 商品名称
    goods_name: str
    # 是否是支付
    is_pay: bool
    # 交易金额
    amount: Amount
    # 支付方式
    pay_source: str
    # 交易状态
    trade_status: str
    # 交易订单号（渠道订单号）
    transaction_id: str
    # 商家订单号
    out_trade_no: str
    # 交易分类，支付宝分类
    category: str


class AlipayImporter(importer.ImporterProtocol):
    """An importer for Alipay CSV files."""

    # 支付宝账单名称匹配正则。 eg. alipay_record_20220825_150818.csv
    FILE_NAME_REGEX = r"^alipay_record_(\d{8})_(\d{6})\.csv$"
    # 账单起始时间匹配
    BILL_DATA_REGEX = r"起始时间：\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+终止时间：\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]"

    def __init__(self, account: str, account_mapping: Dict[str, str] = None, config: Dict[str, Any] = None):
        """
        使用账户和账户映射字典初始化 WeChatPayImporter
        :param account: 微信账户
        :param account_mapping: 其他账户映射字典
        :param config: Importer 配置。
            DISPLAY_META_TIME：元数据中是否包含时间，布尔值
            TAG：标签，为此导入器导入的账单统一添加固定标签，如 wechat
        """
        self.account = account
        self.account_mapping = {
            '余额': account
        }
        if account_mapping:
            self.account_mapping.update(account_mapping)
        self.tags = set()
        self.currency = "CNY"

        self.config = config if config else {}
        self.display_meta_time = self.config.get('DISPLAY_META_TIME', False)
        if 'TAG' in self.config.keys():
            self.tags.add(config['TAG'])

    def identify(self, file):
        # 使用账单文件名称判断能否处理此账单
        match = re.match(AlipayImporter.FILE_NAME_REGEX, path.basename(file.name))
        return bool(match)

    def file_name(self, file):
        with open(file.name, encoding="gbk") as csvfile:
            content = csvfile.read()
            match = re.search(AlipayImporter.BILL_DATA_REGEX, content)
            start_date = parser.parse(match.group(1)).date().strftime('%Y%m%d')
            end_date = parser.parse(match.group(2)).date().strftime('%Y%m%d')
            return f'支付宝账单_{start_date}-{end_date}.csv'

    def file_account(self, _):
        return self.account

    def file_date(self, file):
        # Extract the statement date from the filename.
        match = re.match(AlipayImporter.FILE_NAME_REGEX, path.basename(file.name))
        return datetime.strptime(match.group(1), '%Y%m%d').date()

    def _parse_csv(self, file) -> list[AlipayBillInfo]:
        """解析 CSV 文件，转换成格式良好的 WxPayBillInfo dataclass """
        result = []
        with open(file.name, encoding="gbk") as csvfile:
            # 跳过前两行
            for i in range(2):
                next(csvfile)
            col = ['收/支', '交易对方', '对方账号', '商品说明', '收/付款方式', '金额', '交易状态', '交易分类', '交易订单号', '商家订单号', '交易时间']
            csvreader = csv.DictReader(csvfile, fieldnames=col)
            for row in csvreader:
                # 清理无效字段，跳过无效行
                if None in row:
                    del row[None]
                if not row['交易时间']:
                    continue
                # 由于支付宝对列进行空格填充，所以先处理进行去除空格处理
                row = {k.strip(): v.strip() for k, v in row.items()}

                # 对商品名称进行清洗和截取
                goods_name = row['商品说明']
                goods_name = goods_name if len(goods_name) < 15 else goods_name[0:15] + '...'
                try:
                    # 判断是否是 支出类型账单
                    is_pay = row['收/支'] == '支出'
                    # 解析账单金额
                    amount = row['金额']
                    amount = Amount(D(amount), self.currency)
                    if is_pay:
                        amount = -amount
                except ValueError:
                    continue
                bill = AlipayBillInfo(
                    trade_type=row['收/支'],
                    trade_time=parser.parse(row['交易时间']),
                    payee=row['交易对方'].strip(),
                    goods_name=goods_name.strip(),
                    is_pay=is_pay,
                    amount=amount,
                    pay_source=row['收/付款方式'].strip(),
                    trade_status=row['交易状态'].strip(),
                    transaction_id=row['交易订单号'].strip(),
                    out_trade_no=row['商家订单号'].strip(),
                    category=row['交易分类'].strip(),
                )
                result.append(bill)
        return result

    def extract(self, file, existing_entries=None):
        """
        抽取数据转为账单实体
        :param file:
        :param existing_entries:
        :return:
        """
        entries = []
        bill_list = self._parse_csv(file)
        for index, item in enumerate(bill_list):
            # 定义元数据、账单标记、收款人、账单描述、账单账户等字段默认值
            meta = data.new_metadata(file.name, index)
            if self.display_meta_time:
                meta['time'] = str(item.trade_time.time())

            flag = flags.FLAG_WARNING
            payee = item.payee
            narration = item.goods_name
            account = "Assets:FIXME"
            amount = item.amount
            postings = []

            # 如果支付来源匹配到账户映射，则修改账户为对应的账户
            for pay_source, acct in self.account_mapping.items():
                if pay_source in item.pay_source:
                    flag = flags.FLAG_OKAY
                    account = acct
                    break

            # 开始添加 postings
            postings.append(data.Posting(account, amount, None, None, None, None))

            txn = data.Transaction(
                meta,
                item.trade_time.date(),
                flag,
                payee,
                narration,
                self.tags,
                data.EMPTY_SET,
                postings,
            )
            entries.append(txn)
        return entries
