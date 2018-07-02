import errno
import os
import re
import stat
import subprocess


from shutil import copyfile
from jupyter_core.paths import jupyter_data_dir
from notebook.auth import passwd

# Only (pre)set a password if we're *not* using OpenID Connect
if not (os.getenv('OIDC_DISCOVERY_URI') and
        os.getenv('OIDC_REDIRECT_URI') and
        os.getenv('OIDC_CLIENT_ID') and
        os.getenv('OIDC_CLIENT_SECRET')):

    # Set a password if JUPYTER_PASSWORD is set
    if os.getenv('JUPYTER_PASSWORD'):
        c.NotebookApp.password = passwd(os.getenv('JUPYTER_PASSWORD'))
        del(os.environ['JUPYTER_PASSWORD'])

    # Set Jupyter Notebook Server password to 'jupyter-<Marathon-App-Prefix>'
    # e.g., Marathon App ID '/foo/bar/app' maps to password: 'jupyter-foo-bar'
    if os.getenv('MARATHON_APP_ID'):
        MARATHON_APP_PREFIX = \
            '-'.join(os.getenv('MARATHON_APP_ID').split('/')[:-1])
        c.NotebookApp.password = passwd('jupyter{}'.format(MARATHON_APP_PREFIX))
else:
    # Disable Notebook authentication since we're authenticating using OpenID Connect
    c.NotebookApp.password = u''
    c.NotebookApp.token = u''

# Don't leak OpenID Connect configuration to the end-user
for env in ['OIDC_DISCOVERY_URI',
            'OIDC_REDIRECT_URI',
            'OIDC_CLIENT_ID',
            'OIDC_CLIENT_SECRET',
            'OIDC_EMAIL']:
    try:
        del(os.environ[env])
    except KeyError:
        pass

# Setup the Notebook to listen on localhost:8888 by default
c.NotebookApp.ip = '127.0.0.1'
c.NotebookApp.port = 8888
c.NotebookApp.open_browser = False

# https://github.com/jupyter/notebook/issues/3130
c.FileContentsManager.delete_to_trash = False

# Allow CORS and TLS from behind Nginx/Marathon-LB/HAProxy
# Trust X-Scheme/X-Forwarded-Proto and X-Real-Ip/X-Forwarded-For
# Necessary if the proxy handles SSL
c.NotebookApp.trust_xheaders = True

# Set the Access-Control-Allow-Origin header
c.NotebookApp.allow_origin = '*'

# If running under Apache Mesos:
if (os.getenv('MESOS_SANDBOX')):
    if os.getenv('MARATHON_APP_LABEL_HAPROXY_0_VHOST'):
        c.NotebookApp.allow_origin = \
            'http://{}'.format(os.getenv('MARATHON_APP_LABEL_HAPROXY_0_VHOST'))

    if os.getenv('MARATHON_APP_LABEL_HAPROXY_0_REDIRECT_TO_HTTPS'):
        c.NotebookApp.allow_origin = \
            'https://{}'.format(os.getenv('MARATHON_APP_LABEL_HAPROXY_0_VHOST'))

    # Set the Jupyter Notebook server base URL to the HAPROXY_PATH specified
    if os.getenv('MARATHON_APP_LABEL_HAPROXY_0_PATH'):
        c.NotebookApp.base_url = \
            os.getenv('MARATHON_APP_LABEL_HAPROXY_0_PATH')

    # Tidy up Mesos Env Vars that will interfere with Spark Drivers
    mesos_sandbox = os.getenv('MESOS_SANDBOX')
    os.environ['MESOS_DIRECTORY'] = mesos_sandbox
    try:
        for env in ['MESOS_EXECUTOR_ID',
                    'MESOS_FRAMEWORK_ID',
                    'MESOS_SLAVE_ID',
                    'MESOS_SLAVE_PID'
                    'MESOS_TASK_ID']:
            del os.environ[env]
    except KeyError:
        pass

    # Set the current working directory to ${MESOS_SANDBOX}
    os.chdir(mesos_sandbox)

    # Copy ${MESOS_SANDBOX}/krb5.conf if it exists to /etc/krb5.conf
    if os.path.exists('krb5.conf'):
        copyfile('krb5.conf', '/etc/krb5.conf')

# Build up ${SPARK_OPTS} for Apache Toree and to conveniently reuse with spark-submit:
# eval spark-submit ${SPARK_OPTS} <...>
spark_opts = []

if os.getenv('SPARK_MASTER_URL'):
    spark_opts.append('--master={}'.format(os.getenv('SPARK_MASTER_URL')))

if os.getenv('SPARK_DEPLOY_MODE'):
    spark_opts.append('--deploy-mode={}'.format(os.getenv('SPARK_DEPLOY_MODE')))

if os.getenv('SPARK_CLASS'):
    spark_opts.append('--class={}'.format(os.getenv('SPARK_CLASS')))

if os.getenv('SPARK_APP_NAME'):
    spark_opts.append('--name={}'.format(os.getenv('SPARK_APP_NAME')))

if os.getenv('SPARK_JARS'):
    spark_opts.append('--jars={}'.format(os.getenv('SPARK_JARS')))

if os.getenv('SPARK_PACKAGES'):
    spark_opts.append('--packages={}'.format(os.getenv('SPARK_PACKAGES')))

if os.getenv('SPARK_EXCLUDE_PACKAGES'):
    spark_opts.append('--exclude-packages={}'.format(os.getenv('SPARK_EXCLUDE_PACKAGES')))

if os.getenv('SPARK_REPOSITORIES'):
    spark_opts.append('--repositories={}'.format(os.getenv('SPARK_REPOSITORIES')))

if os.getenv('SPARK_PY_FILES'):
    spark_opts.append('--py-files={}'.format(os.getenv('SPARK_PY_FILES')))

if os.getenv('SPARK_FILES'):
    spark_opts.append('--files={}'.format(os.getenv('SPARK_FILES')))

if os.getenv('SPARK_PROPERTIES_FILE'):
    spark_opts.append('--properties-file={}'.format(os.getenv('SPARK_PROPERTIES_FILE')))

if os.getenv('SPARK_DRIVER_CORES'):
    spark_opts.append('--driver-cores={}'.format(os.getenv('SPARK_DRIVER_CORES')))

if os.getenv('SPARK_DRIVER_MEMORY'):
    spark_opts.append('--driver-memory={}'.format(os.getenv('SPARK_DRIVER_MEMORY')))

if os.getenv('SPARK_DRIVER_JAVA_OPTIONS'):
    spark_opts.append('--driver-java-options={}'.format(os.getenv('SPARK_DRIVER_JAVA_OPTIONS')))

if os.getenv('SPARK_DRIVER_LIBRARY_PATH'):
    spark_opts.append('--driver-library-path={}'.format(os.getenv('SPARK_DRIVER_LIBRARY_PATH')))

if os.getenv('SPARK_DRIVER_CLASS_PATH'):
    spark_opts.append('--driver-class-path={}'.format(os.getenv('SPARK_DRIVER_CLASS_PATH')))

if os.getenv('SPARK_TOTAL_EXECUTOR_CORES'):
    spark_opts.append('--total-executor-cores={}'.format(os.getenv('SPARK_TOTAL_EXECUTOR_CORES')))

if os.getenv('SPARK_EXECUTOR_CORES'):
    spark_opts.append('--executor-cores={}'.format(os.getenv('SPARK_EXECUTOR_CORES')))

if os.getenv('SPARK_EXECUTOR_MEMORY'):
    spark_opts.append('--executor-memory={}'.format(os.getenv('SPARK_EXECUTOR_MEMORY')))

if os.getenv('SPARK_PROXY_USER'):
    spark_opts.append('--proxy-user={}'.format(os.getenv('SPARK_PROXY_USER')))

if os.getenv('SPARK_SUPERVISE'):
    spark_opts.append('--supervise={}'.format(os.getenv('SPARK_SUPERVISE')))

if os.getenv('SPARK_YARN_QUEUE'):
    spark_opts.append('--queue={}'.format(os.getenv('SPARK_YARN_QUEUE')))

if os.getenv('SPARK_YARN_NUM_EXECUTORS'):
    spark_opts.append('--num-executors={}'.format(os.getenv('SPARK_YARN_NUM_EXECUTORS')))

if os.getenv('SPARK_YARN_PRINCIPAL'):
    spark_opts.append('--principal={}'.format(os.getenv('SPARK_YARN_PRINCIPAL')))

if os.getenv('SPARK_YARN_KEYTAB'):
    spark_opts.append('--keytab={}'.format(os.getenv('SPARK_YARN_KEYTAB')))

if os.getenv('PORT_SPARKDRIVER'):
    spark_opts.append('--conf spark.driver.port={}'.format(os.getenv('PORT_SPARKDRIVER')))

if os.getenv('PORT_SPARKBLOCKMANAGER'):
    spark_opts.append('--conf spark.driver.blockManager.port={}'.format(os.getenv('PORT_SPARKBLOCKMANAGER')))

if os.getenv('PORT_SPARKUI'):
    spark_opts.append('--conf spark.ui.port={}'.format(os.getenv('PORT_SPARKUI')))

# Accumulate Spark --conf properties specified in SPARK_CONF_<> env vars
spark_conf_env_pattern = re.compile(r'^SPARK_CONF')
spark_conf_envs = [env for env in os.environ if spark_conf_env_pattern.match(env)]

for env in spark_conf_envs:
    spark_opts.append('--conf {}'.format(os.getenv(env)))

os.environ['SPARK_OPTS'] = ' '.join(spark_opts)
os.environ['PYSPARK_SUBMIT_ARGS'] = ' '.join(spark_opts + ['pyspark-shell'])
os.environ['SPARKR_SUBMIT_ARGS'] = ' '.join(spark_opts + ['sparkr-shell'])

if os.getenv('ENABLE_SPARK_MONITOR'):
    from conda.cli.main_info import get_info_dict
    conda_site_packages = os.path.dirname(get_info_dict()['conda_location'])
    spark_driver_extraclasspath = os.path.join(conda_site_packages, 'sparkmonitor/listener.jar')
    spark_monitor_conf = [
        '--conf spark.driver.extraClassPath={}'.format(spark_driver_extraclasspath),
        '--conf spark.extraListeners=sparkmonitor.listener.JupyterSparkMonitorListener'
    ]
    os.environ['PYSPARK_SUBMIT_ARGS'] = ' '.join(
        spark_opts + spark_monitor_conf + ['pyspark-shell']
    )

if os.getenv('MARATHON_APP_ID'):
    ray_redis_address = ''
    dask_scheduler_address = ''
    if os.getenv('LIBPROCESS_IP') == '0.0.0.0':
        # Use the Spartan autoip address because the container is assigned an IP via CNI
        AUTOIP_SUFFIX = 'marathon.autoip.dcos.thisdcos.directory'
        autoip_prefix = '-'.join(os.getenv('MARATHON_APP_ID').split('/')[::-1][:-1])
        ray_redis_address = '{}.{}:6379'.format(autoip_prefix, AUTOIP_SUFFIX)
        dask_scheduler_address = '{}.{}:8786'.format(autoip_prefix, AUTOIP_SUFFIX)
    else:
        # Use the L4LB address because the container is bound to the agent IP
        L4LB_SUFFIX = 'marathon.l4lb.thisdcos.directory'
        l4lb_prefix = ''.join(os.getenv('MARATHON_APP_ID').split('/')[::1])
        ray_redis_address = '{}.{}:6379'.format(l4lb_prefix, L4LB_SUFFIX)
        dask_scheduler_address = '{}.{}:8786'.format(l4lb_prefix, L4LB_SUFFIX)

    os.environ['RAY_REDIS_ADDRESS'] = ray_redis_address
    os.environ['DASK_SCHEDULER_ADDRESS'] = dask_scheduler_address
else:
    os.environ['RAY_REDIS_ADDRESS'] = '{}:6379'.format(os.getenv('MESOS_CONTAINER_IP'))
    os.environ['DASK_SCHEDULER_ADDRESS'] = '{}:8786'.format(os.getenv('MESOS_CONTAINER_IP'))

# Set a certificate if USE_HTTPS is set to any value
PEM_FILE = os.path.join(jupyter_data_dir(), 'notebook.pem')
if os.getenv('USE_HTTPS'):
    if not os.path.isfile(PEM_FILE):
        # Ensure PEM_FILE directory exists
        DIR_NAME = os.path.dirname(PEM_FILE)
        try:
            os.makedirs(DIR_NAME)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(DIR_NAME):
                pass
            else:
                raise
        # Generate a certificate if one doesn't exist on disk
        subprocess.check_call(['openssl', 'req', '-new', '-newkey', 'rsa:2048',
                               '-days', '365', '-nodes', '-x509', '-subj',
                               '/C=XX/ST=XX/L=XX/O=generated/CN=generated',
                               '-keyout', PEM_FILE, '-out', PEM_FILE])
        # Restrict access to PEM_FILE
        os.chmod(PEM_FILE, stat.S_IRUSR | stat.S_IWUSR)
    c.NotebookApp.certfile = PEM_FILE
