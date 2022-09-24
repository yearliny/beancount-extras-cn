import csv
import datetime
import re
from dataclasses import dataclass
from datetime import datetime
from os import path
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


def parse_csv(file) -> list[WxPayBillInfo]:
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
            bill = WxPayBillInfo(
                trade_time=parser.parse(row['交易时间']),
                trade_type=row['交易类型'],
                payee=row['交易对方'],
                goods_name=goods_name,
                # 判断是否时支出
                is_pay=row['收/支'] in ("支出", "/"),
                amount=row['金额(元)'].lstrip("¥"),
                pay_source=row['支付方式'],
                trade_status=row['当前状态'],
                transaction_id=row['交易单号'],
                out_trade_no=row['商户单号'],
                comment=row['备注']
            )
            result.append(bill)
    return result


class WeChatPayImporter(importer.ImporterProtocol):
    """An importer for WeChat Pay CSV files."""

    FILE_NAME_REGEX = r"^微信支付账单\((\d{8})-(\d{8})\)\.csv$"

    def __init__(self, account: str, account_mapping: Dict[str, str] = None, transaction_tag: str = None):
        """
        使用账户和账户映射字典初始化 WeChatPayImporter
        :param account: 默认账户
        :param account_mapping: 账户映射字典
        """
        self.account = account
        self.account_mapping = account_mapping
        self.tags = set()
        if transaction_tag:
            self.tags.add(transaction_tag)
        self.currency = "CNY"

    def identify(self, file):
        # 使用账单文件名称判断能否处理此账单
        match = re.match(WeChatPayImporter.FILE_NAME_REGEX, path.basename(file.name))
        return bool(match)

    def file_name(self, file):
        return None

    def file_account(self, _):
        return self.account

    def file_date(self, file):
        # Extract the statement date from the filename.
        match = re.match(WeChatPayImporter.FILE_NAME_REGEX, path.basename(file.name))
        return datetime.strptime(match.group(2), '%Y%m%d').date()

    def extract(self, file, existing_entries=None):
        """
        抽取数据转为账单实体
        :param file:
        :param existing_entries:
        :return:
        """
        entries = []
        bill_list = parse_csv(file)
        for index, item in enumerate(bill_list):
            flag = flags.FLAG_WARNING
            meta = data.new_metadata(
                file.name, index, kvlist={"time": str(item.trade_time.time())}
            )

            try:
                amount = Amount(D(item.amount), self.currency)
                if item.is_pay:
                    amount = -amount
            except ValueError:
                continue
            payee = item.payee

            # 清洗账单描述
            narration = item.goods_name

            account = "Assets:FIXME"
            for pay_source, acct in self.account_mapping.items():
                if pay_source in item.pay_source:
                    account = acct
                    flag = flags.FLAG_OKAY
            postings = [data.Posting(account, amount, None, None, None, None)]

            if item.trade_status == "充值完成":
                postings.insert(
                    0,
                    data.Posting(self.account, -amount, None, None, None, None),
                )
                narration = "微信零钱充值"
                payee = None
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
