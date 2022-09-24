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
class WxPayBillInfo:
    trade_time: datetime
    trade_type: str
    payee: str
    goods_name: str
    is_pay: bool
    amount: Amount
    pay_source: str
    trade_status: str
    transaction_id: str
    out_trade_no: str
    comment: str


class WeChatPayImporter(importer.ImporterProtocol):
    """An importer for WeChat Pay CSV files."""

    FILE_NAME_REGEX = r"^微信支付账单\((\d{8})-(\d{8})\)\.csv$"

    def __init__(self, wechat_account: str, account_mapping: Dict[str, str] = None, config: Dict[str, Any] = None):
        """
        使用账户和账户映射字典初始化 WeChatPayImporter
        :param wechat_account: 微信账户
        :param account_mapping: 其他账户映射字典
        :param config: Importer 配置。
            DISPLAY_META_TIME：元数据中是否包含时间，布尔值
            TAG：标签，为此导入器导入的账单统一添加固定标签，如 wechat
        """
        self.wechat_account = wechat_account
        self.account_mapping = account_mapping
        self.tags = set()
        self.config = config if config else {}
        self.currency = "CNY"

        self.display_meta_time = self.config.get('DISPLAY_META_TIME', False)
        if 'TAG' in self.config.keys():
            self.tags.add(config['TAG'])

    def identify(self, file):
        # 使用账单文件名称判断能否处理此账单
        match = re.match(WeChatPayImporter.FILE_NAME_REGEX, path.basename(file.name))
        return bool(match)

    def file_name(self, file):
        return None

    def file_account(self, _):
        return self.wechat_account

    def file_date(self, file):
        # Extract the statement date from the filename.
        match = re.match(WeChatPayImporter.FILE_NAME_REGEX, path.basename(file.name))
        return datetime.strptime(match.group(2), '%Y%m%d').date()

    def _parse_csv(self, file) -> list[WxPayBillInfo]:
        """解析 CSV 文件，转换成格式良好的 WxPayBillInfo dataclass """
        result = []
        with open(file.name, encoding="utf-8") as csvfile:
            for _ in range(16):
                next(csvfile)
            csvreader = csv.DictReader(csvfile)
            for row in csvreader:
                goods_name = row['商品'] \
                    .removeprefix('/') \
                    .removeprefix('转账备注:') \
                    .removeprefix('收款方备注:')
                try:
                    # 判断是否是 支出类型账单
                    is_pay = row['收/支'] == '支出'
                    # 解析账单金额
                    amount = row['金额(元)'].lstrip("¥")
                    amount = Amount(D(amount), self.currency)
                    if is_pay:
                        amount = -amount
                except ValueError:
                    continue
                bill = WxPayBillInfo(
                    trade_time=parser.parse(row['交易时间']),
                    trade_type=row['交易类型'],
                    payee=row['交易对方'],
                    goods_name=goods_name,
                    is_pay=is_pay,
                    amount=amount,
                    pay_source=row['支付方式'],
                    trade_status=row['当前状态'],
                    transaction_id=row['交易单号'],
                    out_trade_no=row['商户单号'],
                    comment=row['备注']
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

            if item.trade_type.startswith('微信红包') or item.trade_type.startswith('零钱提现'):
                payee = None
                narration = item.trade_type

            # 开始添加 postings
            if item.trade_type == '零钱提现':
                # 如果是零钱提现，则添加两笔 posting，分别对应微信账户减少和第三方账户增加
                postings.append(data.Posting(self.wechat_account, -amount, None, None, None, None))
                postings.append(data.Posting(account, amount, None, None, None, None))
            else:
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