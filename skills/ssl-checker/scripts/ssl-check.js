/**
 * SSL证书检查器
 * 用于检查SSL证书有效期并返回结果
 */

const https = require('https');

/**
 * 检查单个域名的SSL证书信息
 * @param {string} hostname - 要检查的主机名或URL
 * @returns {Promise<Object>} 包含证书信息的对象
 */
async function checkSSLCertificate(hostname, port = 443) {
  return new Promise((resolve, reject) => {
    // 解析主机和端口
    let host, parsedPort = port;
    
    if (hostname.includes(':') && !hostname.startsWith('http')) {
      // 如果hostname包含端口号 (如 example.com:8443)
      const parts = hostname.split(':');
      host = parts[0];
      parsedPort = parseInt(parts[1]) || port;
    } else {
      // 处理带协议的URL
      const url = hostname.startsWith('https://') || hostname.startsWith('http://') ? hostname : `https://${hostname}`;
      const parsedUrl = new URL(url);
      host = parsedUrl.host.includes(':') ? parsedUrl.host.split(':')[0] : parsedUrl.host;
      parsedPort = parsedUrl.port ? parseInt(parsedUrl.port) : port;
    }

    const options = {
      host: host,
      port: parsedPort,
      method: 'GET',
      rejectUnauthorized: false // 允许自签名证书
    };

    const req = https.request(options, (res) => {
      const cert = res.connection.getPeerCertificate();
      
      if (!cert || !cert.valid_from || !cert.valid_to) {
        reject(new Error(`无法获取 ${hostname} 的SSL证书信息`));
        return;
      }

      // 计算剩余天数
      const validFrom = new Date(cert.valid_from);
      const validTo = new Date(cert.valid_to);
      const now = new Date();
      const daysLeft = Math.ceil((validTo - now) / (1000 * 60 * 60 * 24));

      resolve({
        hostname: host,
        valid_from: validFrom.toISOString(),
        valid_to: validTo.toISOString(),
        days_left: daysLeft,
        issuer: cert.issuer?.CN || 'Unknown',
        subject: cert.subject?.CN || 'Unknown',
        isValid: daysLeft > 0,
        isExpiringSoon: daysLeft <= 30 // 少于30天视为即将过期
      });
    });

    req.on('error', (err) => {
      reject(err);
    });

    req.setTimeout(10000, () => {
      req.destroy();
      reject(new Error(`请求 ${hostname} 超时`));
    });

    req.end();
  });
}

/**
 * 批量检查多个域名的SSL证书
 * @param {Array<string>} domains - 要检查的域名列表
 * @param {number} warningThreshold - 警告阈值（天）
 * @returns {Promise<Object>} 检查结果对象
 */
async function checkMultipleCertificates(domains, warningThreshold = 30) {
  const results = [];
  const alerts = [];
  
  for (const domain of domains) {
    try {
      // 支持在域名中指定端口，如 example.com:8443
      let hostname = domain;
      let port = 443;
      
      if (typeof domain === 'object' && domain.hostname) {
        hostname = domain.hostname;
        port = domain.port || 443;
      } else if (domain.includes(':') && !domain.startsWith('http')) {
        const parts = domain.split(':', 2);
        hostname = parts[0];
        port = parseInt(parts[1]) || 443;
      }
      
      const certInfo = await checkSSLCertificate(hostname, port);
      certInfo.warningThreshold = warningThreshold;
      certInfo.needsAttention = certInfo.days_left <= warningThreshold;
      
      if (certInfo.needsAttention) {
        alerts.push(certInfo);
      }
      
      results.push(certInfo);
    } catch (error) {
      console.error(`检查 ${domain} 时出错:`, error.message);
      const errorResult = {
        hostname: typeof domain === 'object' ? domain.hostname : domain,
        error: error.message,
        isValid: false,
        needsAttention: true
      };
      alerts.push(errorResult);
      results.push(errorResult);
    }
  }
  
  // 生成摘要
  const summary = {
    totalChecked: results.length,
    validCertificates: results.filter(r => r.isValid && !r.error).length,
    expiringSoon: results.filter(r => r.isExpiringSoon && !r.error).length,
    errors: results.filter(r => r.error).length,
    needsAttention: alerts.length
  };
  
  return {
    results,
    summary,
    alerts,
    timestamp: new Date().toISOString()
  };
}

/**
 * Agent技能的主要执行函数
 * @param {Object} context - MCP上下文对象
 * @param {Object} params - 输入参数
 * @returns {Object} 检查结果
 */
async function execute(context, params) {
  try {
    // 获取输入参数
    const domains = params.domains || [];
    const hostname = params.hostname;  // 单个域名参数
    const port = params.port || 443;  // 端口参数
    const warningThreshold = params.warningThreshold || params.threshold || 30;  // 支持threshold别名
    
    // 优先使用单个域名参数
    if (hostname) {
      // 单个域名检查模式
      const certInfo = await checkSSLCertificate(hostname, port);
      certInfo.warningThreshold = warningThreshold;
      certInfo.needsAttention = certInfo.days_left <= warningThreshold;
      
      const result = {
        results: [certInfo],
        summary: {
          totalChecked: 1,
          validCertificates: certInfo.isValid && !certInfo.error ? 1 : 0,
          expiringSoon: certInfo.isExpiringSoon && !certInfo.error ? 1 : 0,
          errors: certInfo.error ? 1 : 0,
          needsAttention: certInfo.needsAttention ? 1 : 0
        },
        alerts: certInfo.needsAttention ? [certInfo] : [],
        timestamp: new Date().toISOString()
      };
      
      // 使用MCP上下文传递结果
      if (context && typeof context.setOutput === 'function') {
        context.setOutput('ssl_check_result', result);
      }
      
      return {
        success: true,
        data: result,
        message: `SSL证书检查完成：${hostname}:${port}`
      };
    } else if (domains && domains.length > 0) {
      // 批量域名检查模式
      const checkResults = await checkMultipleCertificates(domains, warningThreshold);
      
      // 使用MCP上下文传递结果
      if (context && typeof context.setOutput === 'function') {
        context.setOutput('ssl_check_results', checkResults);
      }
      
      // 返回结果
      return {
        success: true,
        data: checkResults,
        message: `SSL证书检查完成，共检查 ${checkResults.summary.totalChecked} 个域名`
      };
    } else {
      throw new Error('必须提供域名进行SSL证书检查 (使用hostname参数或domains参数)');
    }
  } catch (error) {
    console.error('SSL证书检查过程中出现错误:', error);
    
    const errorResult = {
      success: false,
      error: error.message,
      message: 'SSL证书检查失败'
    };
    
    // 使用MCP上下文传递错误信息
    if (context && typeof context.setError === 'function') {
      context.setError(error.message);
    }
    
    return errorResult;
  }
}

/**
 * 打印格式化的检查结果
 * @param {Object} results - 检查结果
 */
function printResults(results) {
  console.log('\n=== SSL证书检查结果 ===');
  console.log(`检查时间: ${results.timestamp}`);
  console.log('');
  
  console.log('摘要:');
  console.log(`  总计检查: ${results.summary.totalChecked}`);
  console.log(`  有效证书: ${results.summary.validCertificates}`);
  console.log(`  即将过期: ${results.summary.expiringSoon}`);
  console.log(`  检查错误: ${results.summary.errors}`);
  console.log(`  需要关注: ${results.summary.needsAttention}`);
  console.log('');
  
  console.log('详细结果:');
  results.results.forEach(result => {
    if (result.error) {
      console.log(`❌ ${result.hostname}: ${result.error}`);
    } else if (result.needsAttention) {
      console.log(`⚠️ ${result.hostname}: 剩余 ${result.days_left} 天 (${result.valid_to})`);
    } else {
      console.log(`✅ ${result.hostname}: 剩余 ${result.days_left} 天 (${result.valid_to})`);
    }
  });
  
  if (results.alerts.length > 0) {
    console.log('\n需要立即关注:');
    results.alerts.forEach(alert => {
      if (alert.error) {
        console.log(`❌ ${alert.hostname}: ${alert.error}`);
      } else {
        console.log(`⚠️ ${alert.hostname}: 证书将于 ${alert.days_left} 天后过期`);
      }
    });
  }
}

// 新增单域名检查函数
async function checkSingleDomain(hostname, port = 443, threshold = 30) {
  const certInfo = await checkSSLCertificate(hostname, port);
  certInfo.warningThreshold = threshold;
  certInfo.needsAttention = certInfo.days_left <= threshold;
  
  const result = {
    results: [certInfo],
    summary: {
      totalChecked: 1,
      validCertificates: certInfo.isValid && !certInfo.error ? 1 : 0,
      expiringSoon: certInfo.isExpiringSoon && !certInfo.error ? 1 : 0,
      errors: certInfo.error ? 1 : 0,
      needsAttention: certInfo.needsAttention ? 1 : 0
    },
    alerts: certInfo.needsAttention ? [certInfo] : [],
    timestamp: new Date().toISOString()
  };
  
  return result;
}

// 导出主要功能
module.exports = {
  checkSSLCertificate,
  checkMultipleCertificates,
  checkSingleDomain,
  execute,
  printResults
};

// 如果直接运行此脚本，则作为命令行工具执行
if (require.main === module) {
  // 解析命令行参数
  const args = process.argv.slice(2);
  
  if (args.length > 0) {
    // 检查是否有 --port 或 --threshold 参数
    let domains = [];
    let port = 443;
    let threshold = 30;
    
    for (let i = 0; i < args.length; i++) {
      if (args[i] === '--port' && args[i + 1]) {
        port = parseInt(args[++i]);
      } else if (args[i] === '--threshold' && args[i + 1]) {
        threshold = parseInt(args[++i]);
      } else {
        domains.push(args[i]);
      }
    }
    
    if (domains.length === 1) {
      // 单域名检查
      console.log(`正在检查域名: ${domains[0]} (端口: ${port}, 阈值: ${threshold}天)`);
      
      checkSingleDomain(domains[0], port, threshold)
        .then(results => {
          printResults(results);
          // 确保脚本退出
          process.exit(0);
        })
        .catch(error => {
          console.error('检查过程中出现错误:', error.message);
          // 发生错误时也退出
          process.exit(1);
        });
    } else if (domains.length > 1) {
      // 多域名检查
      console.log(`正在检查域名: ${domains.join(', ')} (阈值: ${threshold}天)`);
      
      checkMultipleCertificates(domains, threshold)
        .then(results => {
          printResults(results);
          // 确保脚本退出
          process.exit(0);
        })
        .catch(error => {
          console.error('检查过程中出现错误:', error.message);
          // 发生错误时也退出
          process.exit(1);
        });
    } else {
      console.log('未提供有效的域名');
      process.exit(1);
    }
  } else {
    console.log('用法:');
    console.log('  单域名: node ssl-check.js domain.com [--port 端口号] [--threshold 天数]');
    console.log('  多域名: node ssl-check.js domain1.com domain2.com [--threshold 天数]');
    console.log('');
    console.log('例如:');
    console.log('  node ssl-check.js google.com');
    console.log('  node ssl-check.js google.com --port 443');
    console.log('  node ssl-check.js example.com --port 8443 --threshold 7');
    console.log('  node ssl-check.js google.com github.com --threshold 15');
    // 显示帮助后退出
    process.exit(0);
  }
}