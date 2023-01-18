import os

import kubernetes_asyncio

class K8sUtil:
    @classmethod
    async def on_startup(cls):
        if os.path.exists('/run/secrets/kubernetes.io/serviceaccount'):
            kubernetes_asyncio.config.load_incluster_config()
        else:
            await kubernetes_asyncio.config.load_kube_config()

        cls.core_v1_api = kubernetes_asyncio.client.CoreV1Api()
        cls.custom_objects_api = kubernetes_asyncio.client.CustomObjectsApi()

class K8sObject:
    def __init__(self, definition):
        self.definition = definition

    @property
    def annotations(self):
        return self.metadata.get('annotations', {})

    @property
    def creation_timestamp(self):
        return self.metadata['creationTimestamp']

    @property
    def labels(self):
        return self.metadata.get('labels', {})

    @property
    def metadata(self):
        return self.definition['metadata']

    @property
    def name(self):
        return self.metadata['name']

    @property
    def uid(self):
        return self.metadata['uid']

class K8sClusterObject(K8sObject):
    @classmethod
    async def get(cls, name, namespace=None):
        definition = await K8sUtil.custom_objects_api.get_cluster_custom_object(
            group = cls.group,
            name = name,
            plural = cls.plural,
            version = cls.version,
        )
        return cls(definition)

    async def merge_patch(self, patch):
        definition = await K8sUtil.custom_objects_api.patch_cluster_custom_object(
            group = self.group,
            name = self.name,
            plural = self.plural,
            version = self.version,
            body = patch,
            _content_type = 'application/merge-patch+json',
        )
        self.definition = definition
