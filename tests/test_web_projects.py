import io
import os
import tempfile
import unittest

from imagesorter.web.app import create_app


class WebProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_env = dict(os.environ)
        os.environ['IMAGESORTER_DATA_ROOT'] = self.tmp.name
        os.environ.pop('IMAGESORTER_PASSWORD', None)
        os.environ['IMAGESORTER_SECRET_KEY'] = 'test-secret'
        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)
        self.tmp.cleanup()

    def _upload(self, filename: str, project: str | None = None):
        data = {
            'file': (io.BytesIO(b'fake-image-data'), filename),
        }
        if project:
            data['project'] = project
        return self.client.post('/api/upload', data=data, content_type='multipart/form-data')

    def test_project_create_select_and_isolated_counts(self):
        resp = self.client.get('/api/projects')
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload['active_project'])

        resp = self.client.post('/api/projects', json={'name': 'alpha'})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json()['project'], 'alpha')

        resp = self._upload('alpha.jpg')
        self.assertEqual(resp.status_code, 200)

        counts_alpha = self.client.get('/counts?project=alpha').get_json()
        self.assertEqual(counts_alpha['unlabeled'], 1)

        resp = self.client.post('/api/projects', json={'name': 'beta'})
        self.assertEqual(resp.status_code, 201)

        counts_beta_initial = self.client.get('/counts?project=beta').get_json()
        self.assertEqual(counts_beta_initial['unlabeled'], 0)

        resp = self._upload('beta.jpg', project='beta')
        self.assertEqual(resp.status_code, 200)

        counts_beta = self.client.get('/counts?project=beta').get_json()
        self.assertEqual(counts_beta['unlabeled'], 1)

        counts_alpha_again = self.client.get('/counts?project=alpha').get_json()
        self.assertEqual(counts_alpha_again['unlabeled'], 1)

    def test_input_alias_works_for_read_and_label(self):
        self.client.get('/api/projects')

        resp = self._upload('alias.jpg')
        self.assertEqual(resp.status_code, 200)

        unlabeled = self.client.get('/images?count=10&folder=unlabeled').get_json()
        alias = self.client.get('/images?count=10&folder=input').get_json()
        self.assertEqual(unlabeled['total_available'], alias['total_available'])
        filename = unlabeled['images'][0]

        resp = self.client.post('/api/label', json={'filename': filename, 'label': 'good', 'source': 'input'})
        self.assertEqual(resp.status_code, 200)

        counts = self.client.get('/counts').get_json()
        self.assertEqual(counts['unlabeled'], 0)
        self.assertEqual(counts['good'], 1)


if __name__ == '__main__':
    unittest.main()
