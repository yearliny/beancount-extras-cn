"""从天天基金网获取净值价格"""

import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Optional

import requests
from beancount.prices import source
from dateutil import tz, utils

CN_TZ = tz.gettz("Asia/Shanghai")


class EastMoneyError(ValueError):
    """An error from the EastMoney API."""


class Source(source.Source):
    """
    天天基金 基金/股票/指数 净值数据源
    bean-price -e CNY:beancount_extras_cn.price.eastmoney/F000001
    """

    fund_code_regex = re.compile(r'\d{6}')

    def __init__(self):
        self.http = requests.Session()

    def get_latest_price(self, ticker: str) -> Optional[source.SourcePrice]:
        """See contract in beanprice.source.Source."""
        return self._get_price_series(ticker)

    def get_historical_price(self, ticker: str, time) -> Optional[source.SourcePrice]:
        """See contract in beanprice.source.Source."""
        return self._get_price_series(ticker, time)

    def _get_price_series(self, ticker: str, time=None) -> Optional[source.SourcePrice]:
        """
        获取价格序列
        :param ticker: 股票/基金代码，需要包含六位数字，用正则提取
        :param time: 需要查询的日期
        :return: 查询的结果
        """
        fund_code: str = self.fund_code_regex.search(ticker).group()
        payload = {
            "callback": "thecallback",
            "fundCode": fund_code,
            "pageIndex": 1,
            "pageSize": 1,

        }
        if time is not None:
            datetime_str = time.strftime("%Y-%m-%d")
            payload.update({
                "startDate": datetime_str,
                "endDate": datetime_str,
            })
        response: requests.Response = self.http.get(
            "https://api.fund.eastmoney.com/f10/lsjz",
            params=payload,
            headers={
                "Referer": "https://fundf10.eastmoney.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/106.0.0.0 Safari/537.36 "
            }
        )
        if response.status_code != 200:
            raise EastMoneyError(f"API 返回失败 HTTP 状态码 {response.status_code}！")

        result_str: str = response.text.removeprefix("thecallback(").removesuffix(")")
        result = json.loads(result_str)
        records = result["Data"]["LSJZList"]
        if len(records) == 0:
            raise EastMoneyError("API 没有返回数据！")

        trade_date = records[0]["FSRQ"]
        price = Decimal(records[0]["DWJZ"])
        trade_date = datetime.strptime(trade_date, "%Y-%m-%d")
        trade_date = utils.default_tzinfo(trade_date, CN_TZ)
        return source.SourcePrice(price, trade_date, 'CNY')
