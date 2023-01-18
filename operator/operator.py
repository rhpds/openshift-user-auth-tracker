import kopf
import logging
import os

from datetime import datetime, timezone

import kubernetes_asyncio

from configure_kopf_logging import configure_kopf_logging
from infinite_relative_backoff import InfiniteRelativeBackoff
from k8sutil import K8sClusterObject, K8sUtil

app_domain = os.environ.get('APP_DOMAIN', 'demo.redhat.com')
last_login_annotation = f"{app_domain}/last-login"

class OAuthAccessToken(K8sClusterObject):
    group = 'oauth.openshift.io'
    plural = 'oauthaccesstokens'
    version = 'v1'

    @property
    def user_name(self):
        return self.definition['userName']

class User(K8sClusterObject):
    group = 'user.openshift.io'
    plural = 'users'
    version = 'v1'

    @property
    def last_login(self):
        return self.annotations.get(last_login_annotation)

@kopf.on.startup()
async def configure(settings: kopf.OperatorSettings, **_):
    global core_v1_api, custom_objects_api, operator_namespace

    # Never give up from network errors
    settings.networking.error_backoffs = InfiniteRelativeBackoff()

    # Only create events for warnings and errors
    settings.posting.level = logging.WARNING

    # Disable scanning for CustomResourceDefinitions updates
    settings.scanning.disabled = True

    # Configure logging
    configure_kopf_logging()

    await K8sUtil.on_startup()

@kopf.on.event('oauth.openshift.io', 'v1', 'oauthaccesstokens')
async def oauthaccesstoken_event(event, logger, **_):
    if event['type'] == 'DELETED':
        return

    oauthaccesstoken = OAuthAccessToken(event['object'])

    # kubeadmin user does not have a user object to annotate
    if oauthaccesstoken.user_name == 'kube:admin':
        return

    try:
        user = await User.get(oauthaccesstoken.user_name)
    except kubernetes_asyncio.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning(f"Unable to find user {oauthaccesstoken.user_name}")
            return
        else:
            raise

    if not user.last_login or user.last_login < oauthaccesstoken.creation_timestamp:
        await user.merge_patch({
            "metadata": {
                "annotations": {
                    last_login_annotation: oauthaccesstoken.creation_timestamp
                }
            }
        })
