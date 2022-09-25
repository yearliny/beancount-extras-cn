import os.path
import unittest
from os import path

from beancount.ingest import regression_pytest as regtest

from beancount_extras_cn.importers.alipay import AlipayImporter

account_mapping = {
    '招商银行储蓄卡(1234)': 'Assets:Bank:CMB'
}
IMPORTER = AlipayImporter("Assets:TPP:Alipay", account_mapping)
TEST_DIR = os.path.join(path.dirname(__file__), 'alipay_test_docs')


@regtest.with_importer(IMPORTER)
@regtest.with_testdir(TEST_DIR)
class TestAlipayImporter(regtest.ImporterTestBase):
    pass


if __name__ == '__main__':
    unittest.main()
