import { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  InputNumber,
  message,
  Tag,
  Popconfirm,
  Typography,
  Tabs,
  Statistic,
  Row,
  Col,
  Tooltip,
  Alert,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  ReloadOutlined,
  ClearOutlined,
  DatabaseOutlined,
  LineChartOutlined,
  CloudServerOutlined,
} from '@ant-design/icons';
import {
  testDataApi,
  datasourceApi,
  TestLog,
  TestLogCreate,
  TestMetric,
  TestMetricCreate,
  TestDataStats,
  TestDataSourceConfig,
} from '../services/api';

const { Title, Text } = Typography;
const { TextArea } = Input;

const logLevelColors: Record<string, string> = {
  ERROR: 'red',
  WARN: 'orange',
  INFO: 'blue',
  DEBUG: 'gray',
};

export default function TestDataPage() {
  const [logs, setLogs] = useState<TestLog[]>([]);
  const [metrics, setMetrics] = useState<TestMetric[]>([]);
  const [stats, setStats] = useState<TestDataStats | null>(null);
  const [config, setConfig] = useState<TestDataSourceConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [logModalOpen, setLogModalOpen] = useState(false);
  const [metricModalOpen, setMetricModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('logs');
  const [creatingDatasource, setCreatingDatasource] = useState(false);
  const [logForm] = Form.useForm();
  const [metricForm] = Form.useForm();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [logsRes, metricsRes, statsRes, configRes] = await Promise.all([
        testDataApi.listLogs(undefined, undefined, 100),
        testDataApi.listMetrics(undefined, 100),
        testDataApi.getStats(),
        testDataApi.getConfig(),
      ]);
      setLogs(logsRes.data);
      setMetrics(metricsRes.data);
      setStats(statsRes.data);
      setConfig(configRes.data);
    } catch {
      message.error('加载测试数据失败，请确保 Prometheus 服务已启动');
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    setLoading(true);
    try {
      const result = await testDataApi.regenerate();
      message.success(`已重新生成测试数据: ${result.data.logs_count} 条日志, ${result.data.metrics_count} 条指标`);
      loadData();
    } catch {
      message.error('重新生成失败');
    } finally {
      setLoading(false);
    }
  };

  const handleClearLogs = async () => {
    try {
      await testDataApi.clearLogs();
      message.success('日志已清空');
      loadData();
    } catch {
      message.error('清空失败');
    }
  };

  const handleClearMetrics = async () => {
    try {
      await testDataApi.clearMetrics();
      message.success('指标已清空');
      loadData();
    } catch {
      message.error('清空失败');
    }
  };

  const handleDeleteLog = async (id: string) => {
    try {
      await testDataApi.deleteLog(id);
      message.success('删除成功');
      loadData();
    } catch {
      message.error('删除失败');
    }
  };

  const handleDeleteMetric = async (id: string) => {
    try {
      await testDataApi.deleteMetric(id);
      message.success('删除成功');
      loadData();
    } catch {
      message.error('删除失败');
    }
  };

  const handleCreateLog = async (values: TestLogCreate) => {
    try {
      await testDataApi.createLog(values);
      message.success('添加成功');
      setLogModalOpen(false);
      logForm.resetFields();
      loadData();
    } catch {
      message.error('添加失败');
    }
  };

  const handleCreateMetric = async (values: TestMetricCreate & { labelsStr?: string }) => {
    try {
      // Parse labels from string
      let labels: Record<string, string> = {};
      if (values.labelsStr) {
        values.labelsStr.split(',').forEach(pair => {
          const [key, value] = pair.split('=').map(s => s.trim());
          if (key && value) {
            labels[key] = value.replace(/"/g, '');
          }
        });
      }
      
      await testDataApi.createMetric({
        name: values.name,
        value: values.value,
        type: values.type,
        labels,
      });
      message.success('添加成功');
      setMetricModalOpen(false);
      metricForm.resetFields();
      loadData();
    } catch {
      message.error('添加失败');
    }
  };

  const handleCreateTestDatasources = async () => {
    if (!config || !config.prometheus) {
      message.error('无法获取测试数据源配置');
      return;
    }

    setCreatingDatasource(true);
    try {
      // Create Prometheus data source only (ES disabled due to memory constraints)
      await datasourceApi.create({
        name: '测试 Prometheus',
        type: 'prometheus',
        host: config.prometheus.host,
        port: config.prometheus.port,
      });

      message.success('Prometheus 数据源创建成功！请前往「数据源管理」页面查看');
    } catch {
      message.error('创建数据源失败，可能已存在');
    } finally {
      setCreatingDatasource(false);
    }
  };

  const logColumns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (time: string) => new Date(time).toLocaleString(),
    },
    {
      title: '级别',
      dataIndex: 'level',
      key: 'level',
      width: 80,
      render: (level: string) => (
        <Tag color={logLevelColors[level] || 'default'}>{level}</Tag>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 120,
    },
    {
      title: '消息',
      dataIndex: 'message',
      key: 'message',
      ellipsis: true,
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: unknown, record: TestLog) => (
        <Popconfirm title="确定删除?" onConfirm={() => handleDeleteLog(record.id)}>
          <Button type="link" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ];

  const metricColumns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (time: string) => new Date(time).toLocaleString(),
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
    },
    {
      title: '标签',
      dataIndex: 'labels',
      key: 'labels',
      width: 250,
      render: (labels: Record<string, string>) => (
        <Tooltip title={JSON.stringify(labels)}>
          <Text ellipsis style={{ maxWidth: 230 }}>
            {Object.entries(labels).map(([k, v]) => `${k}="${v}"`).join(', ')}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: '值',
      dataIndex: 'value',
      key: 'value',
      width: 120,
      render: (value: number) => typeof value === 'number' ? value.toFixed(2) : value,
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (type: string) => <Tag>{type}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: unknown, record: TestMetric) => (
        <Popconfirm title="确定删除?" onConfirm={() => handleDeleteMetric(record.id)}>
          <Button type="link" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <Title level={4}>测试数据管理</Title>
          <Text type="secondary">管理测试日志（内存存储）和 Prometheus 指标测试数据</Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading}>
            刷新
          </Button>
          <Popconfirm title="确定重新生成所有测试数据?" onConfirm={handleRegenerate}>
            <Button type="primary" icon={<ReloadOutlined />}>
              重新生成
            </Button>
          </Popconfirm>
        </Space>
      </div>

      {/* Info Alert */}
      <Alert
        message="测试数据存储说明"
        description={
          <div>
            <p style={{ margin: '4px 0' }}>
              <strong>日志</strong>：存储在内存中（Elasticsearch 需要 512MB+ 内存，当前环境资源有限）
            </p>
            <p style={{ margin: '4px 0' }}>
              <strong>指标</strong>：存储在内置 <strong>Prometheus</strong> 容器中
              {config && config.prometheus && (
                <Text code style={{ marginLeft: 8 }}>
                  {config.prometheus.host}:{config.prometheus.port}
                </Text>
              )}
            </p>
          </div>
        }
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        action={
          config && config.prometheus && (
            <Button
              type="primary"
              icon={<CloudServerOutlined />}
              onClick={handleCreateTestDatasources}
              loading={creatingDatasource}
            >
              创建 Prometheus 数据源
            </Button>
          )
        }
      />

      {/* Stats Cards */}
      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="日志总数"
                value={stats.logs_total}
                prefix={<DatabaseOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="错误日志"
                value={stats.logs_by_level.ERROR || 0}
                valueStyle={{ color: '#cf1322' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="指标总数"
                value={stats.metrics_total}
                prefix={<LineChartOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="指标类型数"
                value={Object.keys(stats.metrics_by_name).length}
              />
            </Card>
          </Col>
        </Row>
      )}

      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          tabBarExtraContent={
            activeTab === 'logs' ? (
              <Space>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => {
                    logForm.resetFields();
                    logForm.setFieldsValue({ level: 'INFO', source: 'test-service' });
                    setLogModalOpen(true);
                  }}
                >
                  添加日志
                </Button>
                <Popconfirm title="确定清空所有日志?" onConfirm={handleClearLogs}>
                  <Button danger icon={<ClearOutlined />}>清空</Button>
                </Popconfirm>
              </Space>
            ) : (
              <Space>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => {
                    metricForm.resetFields();
                    metricForm.setFieldsValue({ type: 'gauge', value: 0 });
                    setMetricModalOpen(true);
                  }}
                >
                  添加指标
                </Button>
                <Popconfirm title="确定清空所有指标?" onConfirm={handleClearMetrics}>
                  <Button danger icon={<ClearOutlined />}>清空</Button>
                </Popconfirm>
              </Space>
            )
          }
          items={[
            {
              key: 'logs',
              label: (
                <span>
                  <DatabaseOutlined /> 测试日志 ({logs.length})
                </span>
              ),
              children: (
                <Table
                  columns={logColumns}
                  dataSource={logs}
                  rowKey="id"
                  loading={loading}
                  pagination={{ pageSize: 10 }}
                  size="small"
                />
              ),
            },
            {
              key: 'metrics',
              label: (
                <span>
                  <LineChartOutlined /> Prometheus 指标 ({metrics.length})
                </span>
              ),
              children: (
                <Table
                  columns={metricColumns}
                  dataSource={metrics}
                  rowKey="id"
                  loading={loading}
                  pagination={{ pageSize: 10 }}
                  size="small"
                />
              ),
            },
          ]}
        />
      </Card>

      {/* Add Log Modal */}
      <Modal
        title="添加测试日志"
        open={logModalOpen}
        onCancel={() => setLogModalOpen(false)}
        onOk={() => logForm.submit()}
        width={600}
      >
        <Form form={logForm} layout="vertical" onFinish={handleCreateLog}>
          <Form.Item
            name="level"
            label="日志级别"
            rules={[{ required: true }]}
          >
            <Select
              options={[
                { value: 'ERROR', label: 'ERROR' },
                { value: 'WARN', label: 'WARN' },
                { value: 'INFO', label: 'INFO' },
                { value: 'DEBUG', label: 'DEBUG' },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="source"
            label="来源服务"
            rules={[{ required: true, message: '请输入来源服务' }]}
          >
            <Input placeholder="例如：api-gateway, user-service" />
          </Form.Item>
          <Form.Item
            name="message"
            label="日志内容"
            rules={[{ required: true, message: '请输入日志内容' }]}
          >
            <TextArea
              rows={4}
              placeholder="例如：Connection refused to database server at 10.0.0.5:3306"
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Add Metric Modal */}
      <Modal
        title="添加测试指标"
        open={metricModalOpen}
        onCancel={() => setMetricModalOpen(false)}
        onOk={() => metricForm.submit()}
        width={600}
      >
        <Form form={metricForm} layout="vertical" onFinish={handleCreateMetric}>
          <Form.Item
            name="name"
            label="指标名称"
            rules={[{ required: true, message: '请输入指标名称' }]}
          >
            <Input placeholder="例如：http_requests_total, cpu_usage_percent" />
          </Form.Item>
          <Form.Item
            name="value"
            label="指标值"
            rules={[{ required: true, message: '请输入指标值' }]}
          >
            <InputNumber style={{ width: '100%' }} step={0.01} />
          </Form.Item>
          <Form.Item name="type" label="指标类型">
            <Select
              options={[
                { value: 'gauge', label: 'Gauge (即时值)' },
                { value: 'counter', label: 'Counter (计数器)' },
                { value: 'histogram', label: 'Histogram (直方图)' },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="labelsStr"
            label="标签"
            extra="格式: key1=value1, key2=value2"
          >
            <Input placeholder='例如：service="api-gateway", method="GET"' />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
