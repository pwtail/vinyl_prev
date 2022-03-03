
from setuptools import setup, find_packages

classifiers = [
    "Programming Language :: Python :: 3",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Topic :: Software Development :: Libraries",
    "Topic :: Utilities",
]

with open("README.md", "r") as fp:
    README = fp.read()

setup(name="vinyl",
      version="0.1.0",
      author="Vitalii Abetkin",
      author_email="abvit89s@gmail.ru",
      packages=find_packages(),
      description="vinyl style",
      long_description=README,
      license="MIT",
      classifiers=classifiers)
