# aws-cli-tools
Contains command-line tools for common AWS operations. Useful when integrating operations into pipeline deployments.

## Included tools
*  _cfn-launcher.py_: accepts a CloudFormation template and dynamically determines
whether to create a new stack or update an existing stack. You can also
optionally specify a target S3 bucket and/or key path from which you can store
and launch your CloudFormation template. Additionally, you can specify a file
that contains options such as parameters, policies, and notifications for the
CloudFormation stack.

## Installation
To use these tools, simply clone the repository and set up a Python virtualenv:
1. git clone https://github.com/awsninjas/aws-cli-tools.git
2. cd aws-cli-tools
3. mkdir ./virtualenv
4. virtualenv ./virtualenv
5. pip install -r ./requirements.txt

These tools have all been developed against Python 2.7.10

## Usage
###cfn-launcher.py
   python ./cfn-launcher.py --help
   usage: cfn-launcher.py [-h] [-p PROFILE] [-s S3BUCKET] [-k KEY] [-o OPTIONS] template
   
## Contributions
Please feel free to use, build upon, and enhance these tools.  More will be added over time!  We are gladly accepting pull requests.