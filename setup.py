from setuptools import setup, find_packages

setup(
    name='beancount_extras_cn',
    version='0.1',
    description='A collection of Beancount plugins, for chinese.',
    author='yearliny',
    author_email='yearliny@outlook.com',
    url='https://yearliny.com',
    packages=find_packages(),
    install_requires=[
        "beancount~=2.3.0",
    ]
)
