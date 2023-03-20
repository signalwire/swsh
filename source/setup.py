import os,re
from setuptools import setup

CLASSIFIERS = [
  'Development Status :: 5 - Production/Stable',
  'Intended Audience :: Developers',
  'Intended Audience :: Information Technology',
  'Intended Audience :: Telecommunications Industry',
  'License :: OSI Approved :: MIT License',
  'Natural Language :: English',
  'Topic :: Communications',
  'Topic :: Software Development'
]

setup(
  name='swsh',
  version='0.1.0',
  description='SignalWire interactive SHell',
  #long_description=read('README.md'),
  long_description_content_type="text/markdown",
  classifiers=CLASSIFIERS,
  url='https://github.com/shane-signalwire/swish',
  author='SignalWire Team',
  author_email='open.source@signalwire.com',
  license='MIT',
  install_requires=[
    'signalwire',
    'requests',
    'python-dotenv',
    'cmd2',
    'setuptools',
    'pygments==2.14.0',
  ],
  python_requires='>=3.6',
  zip_safe=False
)
