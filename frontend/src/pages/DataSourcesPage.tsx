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
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ApiOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import {
  datasourceApi,
  DataSource,
  DataSourceCreate,
} from '../services/api';

const { Title, Text } = Typography;

const typeOptions = [
  { value: 'elk', label: 'Elasticsearch / ELK' },
  { value: 'loki', label: 'Grafana Loki' },
  { value: 'prometheus', label: 'Prometheus' },
];

const typeColors: Record<string, string> = {
  elk: 'blue',
  loki: 'green',
  prometheus: 'orange',
};

export default function DataSourcesPage() {
  const [datasources, setDatasources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResults, setTestResults] = useState<Record<number, { success: boolean; message: string }>>({});
  const [form] = Form.useForm();

  useEffect(() => {
    loadDatasources();
  }, []);

  const loadDatasources = async () => {
    setLoading(true);
    try {
      const response = await datasourceApi.list();
      setDatasources(response.data);
    } catch {
      message.error('加载数据源失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingId(null);
    form.resetFields();
    form.setFieldsValue({ port: 9200, type: 'elk', host: '' });
    setModalOpen(true);
  };

  const handleTypeChange = (type: string) => {
    if (type === 'elk') {
      form.setFieldsValue({ port: 9200 });
    } else if (type === 'prometheus') {
      form.setFieldsValue({ port: 9090 });
    } else if (type === 'loki') {
      form.setFieldsValue({ port: 3100 });
    }
  };

  const handleEdit = (record: DataSource) => {
    setEditingId(record.id);
    form.setFieldsValue({
      name: record.name,
      type: record.type,
      host: record.host,
      port: record.port,
      auth_token: record.auth_token,
      index: record.config?.index,
    });
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await datasourceApi.delete(id);
      message.success('删除成功');
      loadDatasources();
    } catch {
      message.error('删除失败');
    }
  };

  const handleTest = async (record: DataSource) => {
    setTestingId(record.id);
    setTestResults((prev) => ({ ...prev, [record.id]: { success: false, message: '测试中...' } }));
    
    try {
      const response = await datasourceApi.test(record.id);
      setTestResults((prev) => ({
        ...prev,
        [record.id]: {
          success: response.data.success,
          message: response.data.message,
        },
      }));
      if (response.data.success) {
        message.success(`连接成功 (${response.data.latency_ms?.toFixed(0)}ms)`);
      } else {
        message.error(response.data.message);
      }
    } catch {
      setTestResults((prev) => ({
        ...prev,
        [record.id]: { success: false, message: '测试失败' },
      }));
      message.error('测试请求失败');
    } finally {
      setTestingId(null);
    }
  };

  const handleSubmit = async (values: DataSourceCreate & { index?: string }) => {
    const data: DataSourceCreate = {
      name: values.name,
      type: values.type,
      host: values.host,
      port: values.port,
      auth_token: values.auth_token,
      config: values.index ? { index: values.index } : undefined,
    };

    try {
      if (editingId) {
        await datasourceApi.update(editingId, data);
        message.success('更新成功');
      } else {
        await datasourceApi.create(data);
        message.success('创建成功');
      }
      setModalOpen(false);
      loadDatasources();
    } catch {
      message.error(editingId ? '更新失败' : '创建失败');
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => (
        <Tag color={typeColors[type]}>
          {typeOptions.find((t) => t.value === type)?.label || type}
        </Tag>
      ),
    },
    {
      title: '地址',
      key: 'address',
      render: (_: unknown, record: DataSource) => `${record.host}:${record.port}`,
    },
    {
      title: '状态',
      key: 'status',
      render: (_: unknown, record: DataSource) => {
        const result = testResults[record.id];
        if (!result) return <Text type="secondary">未测试</Text>;
        if (testingId === record.id) return <LoadingOutlined />;
        return result.success ? (
          <Tag icon={<CheckCircleOutlined />} color="success">
            连接正常
          </Tag>
        ) : (
          <Tag icon={<CloseCircleOutlined />} color="error">
            连接失败
          </Tag>
        );
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (time: string) => new Date(time).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: DataSource) => (
        <Space>
          <Button
            type="link"
            icon={<ApiOutlined />}
            onClick={() => handleTest(record)}
            loading={testingId === record.id}
          >
            测试
          </Button>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此数据源？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <Title level={4}>数据源管理</Title>
          <Text type="secondary">配置日志和指标数据源，用于告警分析时收集上下文</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
          添加数据源
        </Button>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={datasources}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
      </Card>

      <Modal
        title={editingId ? '编辑数据源' : '添加数据源'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        width={500}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="例如：生产环境日志" />
          </Form.Item>
          <Form.Item
            name="type"
            label="类型"
            rules={[{ required: true }]}
          >
            <Select options={typeOptions} disabled={!!editingId} onChange={handleTypeChange} />
          </Form.Item>
          <Form.Item
            name="host"
            label="主机地址"
            rules={[{ required: true, message: '请输入主机地址' }]}
          >
            <Input placeholder="例如：elasticsearch.example.com" />
          </Form.Item>
          <Form.Item
            name="port"
            label="端口"
            rules={[{ required: true, message: '请输入端口' }]}
          >
            <InputNumber style={{ width: '100%' }} min={1} max={65535} />
          </Form.Item>
          <Form.Item name="auth_token" label="认证 Token（可选）">
            <Input.Password placeholder="Bearer Token 或 API Key" />
          </Form.Item>
          <Form.Item
            noStyle
            shouldUpdate={(prev, curr) => prev.type !== curr.type}
          >
            {({ getFieldValue }) =>
              getFieldValue('type') === 'elk' && (
                <Form.Item name="index" label="索引模式（可选）">
                  <Input placeholder="例如：logs-* 或 application-logs" />
                </Form.Item>
              )
            }
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
