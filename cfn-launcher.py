import argparse
import botocore
import boto3
import os
from prettytable import PrettyTable
import sys
import time


def determine_operation(session, cfntemplatename):
    # Check to see if a stack already exists with this provided name:
    operation = ''
    cf = session.resource('cloudformation')
    for stack in cf.stacks.all():
        if stack.name.lower() == cfntemplatename.lower():
            print 'Stack named', cfntemplatename, 'found. Proceeding with UPDATE_STACK operation...'
            operation = 'update'
            break
    if not operation:
        print 'Stack named', cfntemplatename, 'NOT found. Proceeding with CREATE_STACK operation...'
        operation = 'create'
    return operation


def get_bucket(session, s3bucket):
    # Check to see if the provided S3 bucket already exists, if not, create it:
    s3 = session.resource('s3')
    for bucket in s3.buckets.all():
        if bucket.name.lower() == s3bucket.lower():
            print 'S3 bucket named', s3bucket, 'found.'
            return bucket

    print 'S3 bucket named', s3bucket, 'NOT found. Attempting to create it...'
    try:
        bucket = s3.create_bucket(Bucket=s3bucket)
        bucket.wait_until_exists()
        print 'S3 bucket', s3bucket, 'created successfully!'
        return bucket
    except botocore.exceptions.ClientError:
        print 'ERROR: Failed trying to create S3 bucket:', sys.exc_info()[1]
        print 'Exiting with error code 2'
        sys.exit(2)


def upload_template(session, s3bucket, s3location, cfntemplate, cfntemplatefilename):
    # Upload the provided file into the S3 bucket at the provided location:
    s3 = session.resource('s3')

    print 'Uploading CloudFormation template file', cfntemplate, 'to S3 as:', 's3://' + s3bucket.name + '/' + \
                                                                              s3location + cfntemplatefilename
    try:
        data = open(cfntemplate, 'rb')
        s3object = s3bucket.put_object(Key=s3location + cfntemplatefilename, Body=data)

        return s3.meta.client.generate_presigned_url('get_object', Params={'Bucket': s3object.bucket_name,
                                                                           'Key': s3object.key}, ExpiresIn=300)
    except botocore.exceptions.ClientError:
        print 'ERROR: Failed trying to upload template to S3 bucket:', sys.exc_info()[1]
        print 'Exiting with error code 2'
        sys.exit(2)


def upload_files(session, s3bucket, s3location, directory):
    # Upload all files from the provided directory into the S3 bucket at the provided location:
    s3 = session.resource('s3')

    print "Uploading extra files to S3 from:", directory

    try:
        for root, dirs, filenames in os.walk(directory):
            for f in filenames:
                print 'Uploading', f, 'to S3 as:', 's3://' + s3bucket.name + '/' + s3location + root + '/' \
                                                   + f

                data = open(root + '/' + f, 'rb')
                s3bucket.put_object(Key=s3location + root + '/' + f, Body=data)
        return True
    except botocore.exceptions.ClientError:
        print 'ERROR: Failed while uploading extra files to S3 bucket:', sys.exc_info()[1]
        print 'Exiting with error code 2'
        sys.exit(2)


def validate_template(session, cfntemplate, cfntemplate_url):
    # Validate the CloudFormation template using AWS' validation service:
    cf = session.resource('cloudformation')
    print 'Validating CloudFormation template...'
    try:
        if not cfntemplate_url == '':
            # Validates template against pre-signed URL stored in S3:
            validation = cf.meta.client.validate_template(TemplateURL=cfntemplate_url)
        else:
            # Validates template by streaming cfntemplate body, since we are not using S3:
            data = open(cfntemplate, 'rb')
            validation = cf.meta.client.validate_template(TemplateBody=data.read())
        if not validation['ResponseMetadata']['HTTPStatusCode'] == "200":
            print 'CloudFormation template validated successfully!'
            return True
        else:
            print 'ERROR: Template validation failed. HTTP status code:', \
            validation['ResponseMetadata']['HTTPStatusCode']
            print 'Exiting with error code 2'
            sys.exit(2)
    except botocore.exceptions.ClientError:
        print 'ERROR: Template failed validation:', sys.exc_info()[1]
        print 'Exiting with error code 2'
        sys.exit(2)


def launch_stack(session, operation, cfntemplate, cfntemplate_url, cfntemplatename, options):
    # Launches the CloudFormation stack using the provided operation type:
    cf = session.resource('cloudformation')

    if not options == '':
        data = open(options, 'rb')
        options = ', ' + data.read()

    if not cfntemplate_url == '':
        # Uses template uploaded to S3:
        template = 'TemplateURL="' + cfntemplate_url + '"'
    else:
        # Uses template stream from cfntemplate:
        data = open(cfntemplate, 'rb')
        template = 'TemplateBody=data.read()'

    try:
        stack = eval('cf.meta.client.' + operation + '_stack(StackName="' + cfntemplatename + '", ' + template +
                     options + ')')
        if not stack['ResponseMetadata']['HTTPStatusCode'] == "200":
            print 'CloudFormation stack', operation, 'launched successfully!'
            return stack
        else:
            print 'ERROR: CloudFormation stack', operation, 'launch failed. HTTP status code:', \
            stack['ResponseMetadata']['HTTPStatusCode']
            print 'Exiting with error code 2'
            sys.exit(2)
    except botocore.exceptions.ClientError:
        print 'ERROR: Could not ' + operation + ' stack:', sys.exc_info()[1]
        print 'Exiting with error code 2'
        sys.exit(2)


def watch_stack(stack):
    # Watches a stack's operations until it is finished:
    # TODO: Implement this using a waiter function once boto3 supports them for CloudFormation operations
    cf = session.resource('cloudformation')

    while True:
        status = cf.meta.client.describe_stacks(StackName=stack['StackId'])
        simplestatus = status['Stacks'][0]['StackStatus']
        statuscode = simplestatus.split('_')[-1].lower()
        print 'Waiting on stack operations. Current state:', simplestatus

        if (statuscode == 'complete') or (statuscode == 'failed'):
            print 'CloudFormation operations complete.'
            break
        time.sleep(5)

    print 'Stack events:'
    t = PrettyTable(['Timestamp', 'ResourceStatus', 'ResourceType', 'Logical Id', 'Status Reason'])
    t.align = "l"
    for event in cf.meta.client.describe_stack_events(StackName=stack['StackId'])['StackEvents']:
        t.add_row([event.get('Timestamp'), event.get('ResourceStatus'), event.get('ResourceType'),
                   event.get('LogicalResourceId'), event.get('ResourceStatusReason')])
    print t

    if (simplestatus == 'CREATE_COMPLETE') or (simplestatus == 'UPDATE_COMPLETE'):
        print 'Stack operations successful:', simplestatus
        sys.exit(0)
    else:
        print 'Stack operations failed:', simplestatus
        sys.exit(1)

if __name__ == '__main__':
    # Parse our command-line options:
    parser = argparse.ArgumentParser(description='This tool accepts a CloudFormation template and dynamically '
                                                 'determines whether to create a new stack or update an existing '
                                                 'stack. You can also optionally specify a target '
                                                 'S3 bucket and/or key path from which you can store and launch your '
                                                 'CloudFormation template. Additionally, you can specify a file that '
                                                 'contains options such as parameters, policies, and '
                                                 'notifications for the CloudFormation stack.')
    parser.add_argument('-p', '--profile', default='default', help="specifies AWS credentials profile to read from"
                                                                   " ~/.aws/credentials")
    parser.add_argument('-s', '--s3bucket', help="specifies S3 bucket to use when uploading CloudFormation template")
    parser.add_argument('-k', '--key', default='', help="specifies the location (key) within the S3 bucket used to "
                                                        "store the CloudFormation template")
    parser.add_argument('-o', '--options', default='', help="a file containing the CloudFormation stack options, "
                                                            "such as parameters, policies, notifications, etc.")
    parser.add_argument('-f', '--files', default='', help="a directory containing extra files to upload to the provided"
                                                          " S3 bucket. Useful for Lambda functions deployed via "
                                                          "CloudFormation or any other template dependencies.")
    parser.add_argument('template', help="specifies CloudFormation template file")
    args = parser.parse_args()

    # Friendly vars:
    profile = args.profile
    cfntemplate = args.template
    cfntemplatefilename = os.path.basename(cfntemplate)
    cfntemplatename = os.path.splitext(cfntemplatefilename)[0]
    cfntemplate_url = ''
    options = args.options
    extrafiles = args.files
    extrafiles = extrafiles.rstrip('/')
    extrafiles += '/'
    s3bucket = args.s3bucket
    s3location = args.key.lstrip('/')
    s3location = s3location.rstrip('/')
    s3location += '/'

    # Validate that the CloudFormation template file exists:
    if not os.path.isfile(cfntemplate):
        print 'ERROR: Template file', cfntemplate, 'was not found or is not a file.'
        sys.exit(2)

    # Validate that the extrafiles directory exists (if we were supplied one), and make sure we also received a S3
    # bucket as a parameter:
    if not extrafiles == '':
        if not os.path.isdir(extrafiles):
            print 'ERROR: Extra files directory', extrafiles, 'was not found or is not a directory.'
            sys.exit(2)
        if not s3bucket:
            print 'ERROR: You MUST specify a S3 bucket when using the -f or --files option.'
            sys.exit(2)

    # Validate that the options file exists (if we were supplied one):
    if not options == '':
        if not os.path.isfile(options):
            print 'ERROR: Options file', options, 'was not found or is not a file.'
            sys.exit(2)

    # Connect to AWS using provided profile:
    session = boto3.Session(profile_name=profile)
    print 'Connected to AWS using credentials profile: ', profile

    # If user specified a S3 bucket, check to see if S3 bucket exists. If not, create it.
    # If user did not specify a S3 bucket, fall back to command-line, string-passing behavior (has size limit of 51200
    # bytes):
    if s3bucket:
        print 'User specified S3 bucket, looking for it...'
        s3bucket = get_bucket(session, s3bucket)
        print 'Proceeding with S3 bucket', s3bucket.name

        # Now that we have a bucket, upload the template:
        cfntemplate_url = upload_template(session, s3bucket, s3location, cfntemplate, cfntemplatefilename)
        print 'Template uploaded to S3 and pre-signed URL created successfully!'
    else:
        print 'User did not specify S3 bucket, using AWS default...'

    # Validate the CloudFormation template against the CloudFormation service:
    valid = validate_template(session, cfntemplate, cfntemplate_url)

    # Upload extra files (if directory has been provided):
    if not extrafiles == '':
        upload_files(session, s3bucket, s3location, extrafiles)

    # Determine whether this will be a create or an update stack operation:
    operation = determine_operation(session, cfntemplatename)

    # Launch stack:
    stack = launch_stack(session, operation, cfntemplate, cfntemplate_url, cfntemplatename, options)

    # Monitor progress:
    watch_stack(stack)

