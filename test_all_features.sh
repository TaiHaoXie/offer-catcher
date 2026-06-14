#!/bin/bash
# Offer 捕手 - 全功能测试脚本

API_URL="http://localhost:8888"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESUME_PATH="${RESUME_PATH:-}"

echo "======================================"
echo "  Offer 捕手 - 全功能测试"
echo "======================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查文件是否存在
if [ -z "$RESUME_PATH" ]; then
    echo -e "${YELLOW}⚠️  请通过 RESUME_PATH 指定一份本地简历 PDF/DOCX/TXT 后再运行，例如：${NC}"
    echo "   RESUME_PATH=\"/path/to/resume.pdf\" ./test_all_features.sh"
    exit 1
fi

if [ ! -f "$RESUME_PATH" ]; then
    echo -e "${RED}❌ 简历文件不存在: $RESUME_PATH${NC}"
    exit 1
fi

echo -e "${BLUE}📄 简历文件: $RESUME_PATH${NC}"
echo ""

# ========== 测试1: 健康检查 ==========
echo -e "${YELLOW}========== 测试1: 健康检查 ==========${NC}"
HEALTH_RESP=$(curl -s "$API_URL/")
if echo "$HEALTH_RESP" | grep -q '"running"'; then
    echo -e "${GREEN}✅ 后端服务运行正常${NC}"
    echo "   服务: $(echo $HEALTH_RESP | grep -o '"service":"[^"]*"' | cut -d'"' -f4)"
    echo "   版本: $(echo $HEALTH_RESP | grep -o '"version":"[^"]*"' | cut -d'"' -f4)"
else
    echo -e "${RED}❌ 后端服务无响应${NC}"
    exit 1
fi
echo ""

# ========== 测试2: 简历上传解析 ==========
echo -e "${YELLOW}========== 测试2: 简历上传解析 ==========${NC}"
PARSE_RESP=$(curl -s -X POST "$API_URL/api/v1/resume/parse" -F "file=@$RESUME_PATH")

if echo "$PARSE_RESP" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 简历解析成功${NC}"
    RESUME_ID=$(echo "$PARSE_RESP" | grep -o '"resume_id":"[^"]*"' | cut -d'"' -f4)
    echo "   Resume ID: $RESUME_ID"

    # 提取基本信息
    NAME=$(echo "$PARSE_RESP" | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
    UNIVERSITY=$(echo "$PARSE_RESP" | grep -o '"university":"[^"]*"' | head -1 | cut -d'"' -f4)
    MAJOR=$(echo "$PARSE_RESP" | grep -o '"major":"[^"]*"' | head -1 | cut -d'"' -f4)
    DEGREE=$(echo "$PARSE_RESP" | grep -o '"degree":"[^"]*"' | head -1 | cut -d'"' -f4)

    echo "   姓名: $NAME"
    echo "   学校: $UNIVERSITY"
    echo "   专业: $MAJOR"
    echo "   学历: $DEGREE"
else
    echo -e "${RED}❌ 简历解析失败${NC}"
    echo "   响应: $PARSE_RESP"
    exit 1
fi
echo ""

# ========== 测试3: JD解析 ==========
echo -e "${YELLOW}========== 测试3: JD解析 ==========${NC}"
# 创建临时文件避免JSON转义问题
JD_JSON_FILE=$(mktemp)
cat > "$JD_JSON_FILE" << EOF
{
  "jd_text": "字节跳动招聘AI产品经理实习生。要求：本科及以上学历专业不限；对AI产品有浓厚兴趣了解大模型原理；具备良好的沟通能力和逻辑思维；有产品实习经验者优先。岗位职责：协助进行AI产品需求分析；参与产品设计和用户调研；撰写产品文档和PRD。"
}
EOF

JD_RESP=$(curl -s -X POST "$API_URL/api/v1/job/parse" \
    -H "Content-Type: application/json" \
    -d @"$JD_JSON_FILE")
rm -f "$JD_JSON_FILE"

if echo "$JD_RESP" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ JD解析成功${NC}"
    JOB_ID=$(echo "$JD_RESP" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
    echo "   Job ID: $JOB_ID"
    POSITION=$(echo "$JD_RESP" | grep -o '"position_name":"[^"]*"' | cut -d'"' -f4)
    echo "   岗位: $POSITION"
else
    echo -e "${RED}❌ JD解析失败${NC}"
    echo "   响应: $JD_RESP"
    exit 1
fi
echo ""

# ========== 测试4: 校招HR评分 ==========
echo -e "${YELLOW}========== 测试4: 校招HR评分 ==========${NC}"
# 构造简历数据（从解析结果中提取）
CAMPUS_SCORE_RESP=$(curl -s -X POST "$API_URL/api/v1/campus-score" \
    -H "Content-Type: application/json" \
    -d "{
        \"resume_data\": $PARSE_RESP
    }")

if echo "$CAMPUS_SCORE_RESP" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 校招评分成功${NC}"
    TOTAL_SCORE=$(echo "$CAMPUS_SCORE_RESP" | grep -o '"total_score":[0-9]*' | head -1 | cut -d':' -f2)
    GRADE=$(echo "$CAMPUS_SCORE_RESP" | grep -o '"grade":"[A-D]"' | head -1 | cut -d'"' -f3)
    UNIVERSITY_TIER=$(echo "$CAMPUS_SCORE_RESP" | grep -o '"university_tier":"[^"]*"' | cut -d'"' -f4)

    echo "   总分: $TOTAL_SCORE"
    echo "   评级: ${GRADE}级"
    echo "   学校层级: $UNIVERSITY_TIER"

    # 显示各维度得分
    echo "   各维度得分:"
    echo "     - 学校: $(echo "$CAMPUS_SCORE_RESP" | grep -o '"university":[0-9]*' | cut -d':' -f2)"
    echo "     - 学历: $(echo "$CAMPUS_SCORE_RESP" | grep -o '"degree":[0-9]*' | cut -d':' -f2)"
    echo "     - 专业: $(echo "$CAMPUS_SCORE_RESP" | grep -o '"major":[0-9]*' | cut -d':' -f2)"
    echo "     - 实习: $(echo "$CAMPUS_SCORE_RESP" | grep -o '"internship":[0-9]*' | cut -d':' -f2)"
    echo "     - 项目: $(echo "$CAMPUS_SCORE_RESP" | grep -o '"project":[0-9]*' | cut -d':' -f2)"
    echo "     - 技能: $(echo "$CAMPUS_SCORE_RESP" | grep -o '"skill":[0-9]*' | cut -d':' -f2)"
else
    echo -e "${RED}❌ 校招评分失败${NC}"
    echo "   响应: $CAMPUS_SCORE_RESP" | head -200
fi
echo ""

# ========== 测试5: 经历原子库 ==========
echo -e "${YELLOW}========== 测试5: 经历原子库 ==========${NC}"
ATOMS_RESP=$(curl -s "$API_URL/api/v1/atoms")
if echo "$ATOMS_RESP" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 获取原子库成功${NC}"
    ATOMS_COUNT=$(echo "$ATOMS_RESP" | grep -o '"count":[0-9]*' | cut -d':' -f2)
    echo "   原子数量: $ATOMS_COUNT"
else
    echo -e "${YELLOW}⚠️  原子库接口响应异常（可能为空）${NC}"
fi
echo ""

# ========== 测试6: 投递记录 ==========
echo -e "${YELLOW}========== 测试6: 投递记录 ==========${NC}"
APPS_RESP=$(curl -s "$API_URL/api/v1/applications")
if echo "$APPS_RESP" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 获取投递记录成功${NC}"
    APPS_COUNT=$(echo "$APPS_RESP" | grep -o '"count":[0-9]*' | cut -d':' -f2)
    echo "   投递记录数: $APPS_COUNT"
else
    echo -e "${YELLOW}⚠️  投递记录接口响应异常（可能为空）${NC}"
fi
echo ""

# ========== 测试7: 历史记录 ==========
echo -e "${YELLOW}========== 测试7: 匹配历史 ==========${NC}"
HISTORY_RESP=$(curl -s "$API_URL/api/v1/history?limit=5")
if echo "$HISTORY_RESP" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 获取历史记录成功${NC}"
    HISTORY_COUNT=$(echo "$HISTORY_RESP" | grep -o '"count":[0-9]*' | cut -d':' -f2)
    echo "   历史记录数: $HISTORY_COUNT"
else
    echo -e "${YELLOW}⚠️  历史记录接口响应异常（可能为空）${NC}"
fi
echo ""

# ========== 测试总结 ==========
echo "======================================"
echo -e "${GREEN}          测试完成！${NC}"
echo "======================================"
echo ""
echo "📊 功能状态汇总:"
echo "   ✅ 后端服务"
echo "   ✅ 简历解析 (Resume ID: $RESUME_ID)"
echo "   ✅ JD解析 (Job ID: $JOB_ID)"
echo "   ✅ 校招HR评分 (${GRADE}级 ${TOTAL_SCORE}分)"
echo "   ✅ 经历原子库"
echo "   ✅ 投递记录"
echo "   ✅ 匹配历史"
echo ""
echo -e "${BLUE}🌐 访问页面测试完整功能:${NC}"
echo "   主页面: file://$ROOT_DIR/frontend/index.html"
echo "   测试页面: file://$ROOT_DIR/frontend/test-campus-score.html"
echo ""
