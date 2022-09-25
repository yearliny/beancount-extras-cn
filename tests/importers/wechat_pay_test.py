import os
import unittest
from os import path

from beancount.ingest import regression_pytest as regtest

from beancount_extras_cn.importers import WeChatPayImporter

accountDict = {
    "招商银行(1234)": "Assets:Bank:CMB",
    "零钱": "Assets:TPP:Wechat",
}
IMPORTER = WeChatPayImporter("Assets:TPP:Wechat", accountDict)
TEST_DIR = os.path.join(path.dirname(__file__), 'wechat_pay_test_docs')


@regtest.with_importer(IMPORTER)
@regtest.with_testdir(TEST_DIR)
class TestWeChatPayImporter(regtest.ImporterTestBase):
    pass


if __name__ == '__main__':
    unittest.main()
