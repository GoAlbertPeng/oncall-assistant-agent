import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Input,
  Button,
  Space,
  Typography,
  Divider,
  Tag,
  List,
  message,
  Spin,
  Progress,
  Collapse,
  Alert,
  Modal,
  Form,
  Select,
} from 'antd';
import {
  SendOutlined,
  FileAddOutlined,
  HistoryOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  BulbOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import {
  analysisApi,
  ticketApi,
  AnalysisResponse,
  AnalysisListItem,
} from '../services/api';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

const categoryMap: Record<string, { label: string; color: string }> = {
  code_issue: { label: '代码问题', color: 'red' },
  config_issue: { label: '配置问题', color: 'orange' },
  resource_bottleneck: { label: '资源瓶颈', color: 'blue' },
  dependency_failure: { label: '依赖故障', color: 'purple' },
};

export default function AnalysisPage() {
  const navigate = useNavigate();
  const [alertContent, setAlertContent] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [history, setHistory] = useState<AnalysisListItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [ticketModalOpen, setTicketModalOpen] = useState(false);
  const [ticketForm] = Form.useForm();

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    setLoadingHistory(true);
    try {
      const response = await analysisApi.list(1, 10);
      setHistory(response.data);
    } catch {
      // Ignore error
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleAnalyze = async () => {
    if (!alertContent.trim()) {
      message.warning('请输入告警信息');
      return;
    }

    setAnalyzing(true);
    setResult(null);

    try {
      const response = await analysisApi.create({
        alert_content: alertContent,
        time_range_minutes: 30,
      });
      setResult(response.data);
      loadHistory();
      message.success('分析完成');
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || '分析失败');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleViewHistory = async (item: AnalysisListItem) => {
    try {
      const response = await analysisApi.get(item.id);
      setResult(response.data);
      setAlertContent(response.data.alert_content);
    } catch {
      message.error('加载失败');
    }
  };

  const handleCreateTicket = () => {
    if (!result?.analysis_result) {
      message.warning('请先进行告警分析');
      return;
    }
    ticketForm.setFieldsValue({
      title: alertContent.slice(0, 50),
      root_cause: result.analysis_result.root_cause,
      level: 'P3',
    });
    setTicketModalOpen(true);
  };

  const submitTicket = async (values: { title: string; root_cause: string; level: 'P1' | 'P2' | 'P3' }) => {
    try {
      const response = await ticketApi.create({
        session_id: result?.id,
        ...values,
      });
      message.success(`工单创建成功: ${response.data.ticket_no}`);
      setTicketModalOpen(false);
      navigate(`/tickets/${response.data.ticket_no}`);
    } catch {
      message.error('创建工单失败');
    }
  };

  return (
    <div>
      <Title level={4}>智能告警分析</Title>
      <Text type="secondary">输入告警信息，系统将自动收集上下文并分析根因</Text>

      <div style={{ display: 'flex', gap: 24, marginTop: 24 }}>
        {/* 左侧：输入和结果 */}
        <div style={{ flex: 1 }}>
          <Card title="告警信息">
            <TextArea
              rows={4}
              placeholder="请输入告警信息，例如：支付服务 CPU 使用率 99%，持续 5 分钟"
              value={alertContent}
              onChange={(e) => setAlertContent(e.target.value)}
              disabled={analyzing}
            />
            <div style={{ marginTop: 16, textAlign: 'right' }}>
              <Space>
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleAnalyze}
                  loading={analyzing}
                >
                  {analyzing ? '分析中...' : '开始分析'}
                </Button>
                <Button
                  icon={<FileAddOutlined />}
                  onClick={handleCreateTicket}
                  disabled={!result?.analysis_result}
                >
                  生成工单
                </Button>
              </Space>
            </div>
          </Card>

          {analyzing && (
            <Card style={{ marginTop: 16 }}>
              <div style={{ textAlign: 'center' }}>
                <Spin size="large" />
                <div style={{ marginTop: 16 }}>
                  <Progress percent={30} status="active" showInfo={false} />
                  <Text type="secondary">正在收集数据源上下文并分析...</Text>
                </div>
              </div>
            </Card>
          )}

          {result && (
            <>
              {/* 上下文数据 */}
              {result.context_data && (
                <Card title="收集的上下文" style={{ marginTop: 16 }}>
                  <Collapse
                    items={[
                      {
                        key: 'logs',
                        label: `相关日志 (${result.context_data.logs.length} 条)`,
                        children: result.context_data.logs.length > 0 ? (
                          <List
                            size="small"
                            dataSource={result.context_data.logs.slice(0, 20)}
                            renderItem={(log) => (
                              <List.Item>
                                <Text code style={{ fontSize: 12 }}>
                                  [{log.timestamp}] [{log.level}] {log.message}
                                </Text>
                              </List.Item>
                            )}
                          />
                        ) : (
                          <Text type="secondary">无相关日志</Text>
                        ),
                      },
                      {
                        key: 'metrics',
                        label: `相关指标 (${result.context_data.metrics.length} 个)`,
                        children: result.context_data.metrics.length > 0 ? (
                          <pre style={{ fontSize: 12, maxHeight: 200, overflow: 'auto' }}>
                            {JSON.stringify(result.context_data.metrics, null, 2)}
                          </pre>
                        ) : (
                          <Text type="secondary">无相关指标</Text>
                        ),
                      },
                      {
                        key: 'status',
                        label: '数据源状态',
                        children: (
                          <div>
                            {Object.entries(result.context_data.collection_status).map(([key, value]) => (
                              <div key={key}>
                                <Text strong>{key}:</Text> <Text>{value}</Text>
                              </div>
                            ))}
                          </div>
                        ),
                      },
                    ]}
                  />
                </Card>
              )}

              {/* 分析结果 */}
              {result.analysis_result && (
                <Card title="分析结果" style={{ marginTop: 16 }}>
                  <Alert
                    message={
                      <Space>
                        <span>根因分类:</span>
                        <Tag color={categoryMap[result.analysis_result.category]?.color || 'default'}>
                          {categoryMap[result.analysis_result.category]?.label || result.analysis_result.category}
                        </Tag>
                        {result.analysis_result.confidence && (
                          <Text type="secondary">
                            置信度: {(result.analysis_result.confidence * 100).toFixed(0)}%
                          </Text>
                        )}
                      </Space>
                    }
                    type="info"
                    style={{ marginBottom: 16 }}
                  />

                  <Divider orientation="left">
                    <ExclamationCircleOutlined /> 根因结论
                  </Divider>
                  <Paragraph>{result.analysis_result.root_cause}</Paragraph>

                  <Divider orientation="left">
                    <CheckCircleOutlined /> 证据说明
                  </Divider>
                  <Paragraph>{result.analysis_result.evidence}</Paragraph>

                  <Divider orientation="left">
                    <BulbOutlined /> 临时缓解方案
                  </Divider>
                  <Paragraph>{result.analysis_result.temporary_solution}</Paragraph>

                  <Divider orientation="left">
                    <ToolOutlined /> 根本解决方案
                  </Divider>
                  <Paragraph>{result.analysis_result.permanent_solution}</Paragraph>
                </Card>
              )}
            </>
          )}
        </div>

        {/* 右侧：历史记录 */}
        <div style={{ width: 300 }}>
          <Card
            title={
              <Space>
                <HistoryOutlined />
                <span>历史记录</span>
              </Space>
            }
            loading={loadingHistory}
          >
            <List
              size="small"
              dataSource={history}
              locale={{ emptyText: '暂无历史记录' }}
              renderItem={(item) => (
                <List.Item
                  style={{ cursor: 'pointer' }}
                  onClick={() => handleViewHistory(item)}
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        <Text ellipsis style={{ maxWidth: 180 }}>
                          {item.alert_content}
                        </Text>
                        {item.has_result && <CheckCircleOutlined style={{ color: '#52c41a' }} />}
                      </Space>
                    }
                    description={new Date(item.created_at).toLocaleString()}
                  />
                </List.Item>
              )}
            />
          </Card>
        </div>
      </div>

      {/* 创建工单弹窗 */}
      <Modal
        title="创建工单"
        open={ticketModalOpen}
        onCancel={() => setTicketModalOpen(false)}
        onOk={() => ticketForm.submit()}
      >
        <Form form={ticketForm} layout="vertical" onFinish={submitTicket}>
          <Form.Item
            name="title"
            label="工单标题"
            rules={[{ required: true, message: '请输入工单标题' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="root_cause"
            label="根因结论"
          >
            <TextArea rows={3} />
          </Form.Item>
          <Form.Item
            name="level"
            label="故障等级"
            rules={[{ required: true }]}
          >
            <Select>
              <Select.Option value="P1">P1 - 紧急</Select.Option>
              <Select.Option value="P2">P2 - 重要</Select.Option>
              <Select.Option value="P3">P3 - 一般</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
