from http.server import BaseHTTPRequestHandler
import json
from datetime import datetime

class handler(BaseHTTPRequestHandler):
    """APAC Stats API - Vercel Serverless Python Function"""

    def _set_headers(self, status=200, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/' or self.path == '/api/health':
            self._set_headers()
            self.wfile.write(json.dumps({
                'status': 'ok',
                'service': 'APAC Stats API',
                'version': '2.0.0',
                'timestamp': datetime.now().isoformat()
            }).encode('utf-8'))

        elif self.path == '/api/metrics':
            self._set_headers()
            self.wfile.write(json.dumps({
                'indicators': [
                    {'name': 'GDP（亚太区域）', 'value': 28.6, 'unit': '万亿 USD', 'change': 4.2, 'direction': 'up', 'sparkline': [20, 22, 21, 23, 24, 25, 26, 27, 28, 28.6]},
                    {'name': '贸易总额', 'value': 7.3, 'unit': '万亿 USD', 'change': 3.8, 'direction': 'up', 'sparkline': [5.8, 6.0, 6.2, 6.4, 6.6, 6.8, 7.0, 7.1, 7.2, 7.3]},
                    {'name': 'CPI 均值', 'value': 3.1, 'unit': '%', 'change': -2.1, 'direction': 'down', 'sparkline': [3.8, 3.7, 3.6, 3.5, 3.4, 3.3, 3.2, 3.2, 3.1, 3.1]},
                    {'name': '直接投资 FDI', 'value': 1520, 'unit': '亿 USD', 'change': 5.6, 'direction': 'up', 'sparkline': [1200, 1250, 1300, 1350, 1380, 1420, 1460, 1490, 1510, 1520]}
                ]
            }).encode('utf-8'))

        elif self.path == '/api/sources':
            self._set_headers()
            self.wfile.write(json.dumps({
                'sources': [
                    {'name': '世界银行（亚太）', 'active': True, 'last_sync': '2024-11-15 08:30'},
                    {'name': 'IMF 亚太区域报告', 'active': True, 'last_sync': '2024-11-14 16:00'},
                    {'name': 'UN Comtrade 贸易数据', 'active': True, 'last_sync': '2024-11-15 06:00'},
                    {'name': 'ADB 亚洲发展银行', 'active': False, 'last_sync': '2024-11-10 12:00'}
                ]
            }).encode('utf-8'))

        elif self.path == '/api/activities':
            self._set_headers()
            self.wfile.write(json.dumps({
                'activities': [
                    {'time': '10:32', 'text': '完成查询：东盟GDP排名分析'},
                    {'time': '09:15', 'text': '数据源「海关统计月报」已更新'},
                    {'time': '08:40', 'text': '统计公报「2024Q3区域概览」已发布'},
                    {'time': '08:05', 'text': '数据采集任务「RCEP贸易数据」完成'},
                    {'time': '07:50', 'text': '完成查询：中日韩贸易对比'}
                ]
            }).encode('utf-8'))

        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({
                'error': 'Not Found',
                'message': f'Endpoint {self.path} not found'
            }).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._set_headers(400)
            self.wfile.write(json.dumps({'error': 'Invalid JSON'}).encode('utf-8'))
            return

        if self.path == '/api/query':
            self._set_headers()
            self.wfile.write(json.dumps({
                'status': 'processing',
                'query': data.get('query', ''),
                'message': 'Query received and processing'
            }).encode('utf-8'))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not Found'}).encode('utf-8'))
