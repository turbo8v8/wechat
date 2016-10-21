# -*- coding: utf-8 -*-
from wsgiref.simple_server import make_server
import json,time,hashlib
from urllib import request,parse

# 用于解析微信服务器发送过来的xml消息
try: 
  import xml.etree.cElementTree as etree
except ImportError: 
  import xml.etree.ElementTree as etree

# 微信要求的token，在公众号设置里自定义的字符串
token='your token'
# 用于缓存从微信服务器获取的token
access_token=""
# 用于记录token过期时间
tokentime=time.time()
# 微信公众号appid
appid="your appid"
# 微信公众号secret
secret="your secret"
# 微信access_token获取地址
get_token_URL="https://api.weixin.qq.com/cgi-bin/token"
# 微信消息接口地址
message_URL='https://api.weixin.qq.com/cgi-bin/message/custom/send'
# 简单验证，调用自己包装过的接口时作为认证用
callcode="make your callcode"

'''Tools function'''
# 把html请求中的参数从字符串中提取出来,以dict形式返回
def get_parameters(QUERY_STRING):
    data={}
    for x in QUERY_STRING.split("&"):
        if(len(x.split('='))==2):
            data[x.split('=')[0]]=x.split('=')[1]
            # 故意多写几个等号的怎么处理，有时间找个框架翻一下源码看看咋搞的？
    return data

# 验证callcode是否正确
def checkcallcode(QUERY_STRING):
    data=get_parameters(QUERY_STRING)
    return not('callcode' in data and data['callcode']==parse.quote(callcode))

# 微信服务器验证
def wechat_check(data):
    if(not ('timestamp' in data and 'nonce' in data and 'signature' in data)):
        return Flase
    tokenlist=[token,data['timestamp'],data['nonce']]
    tokenlist.sort()
    '''
    python2中正常的，换到python3用map函数分别update最后得出的结果不对了，原因未找到，拼接后一次update正常
    sha1=hashlib.sha1()
    map(sha1.update,tokenlist)
    '''
    tmp_str=''.join(tokenlist)
    # 换到python3后需编码
    return hashlib.sha1(tmp_str.encode('utf-8')).hexdigest()==data['signature']

# 获取token用于调用接口，若过期则去微信服务器重新获取
def get_access_token():
    global tokentime
    global access_token
    # 有access_token并且未过期，直接返回现有的access_token
    if(time.time()<tokentime and len(access_token)>3):
        return access_token
    values={'appid':appid,
            'secret':secret,
            'grant_type':'client_credential'}
    data=parse.urlencode(values).encode('utf8')
    req=request.Request(get_token_URL,data)
    res=request.urlopen(req)
    json_data=json.loads(res.read().decode('utf-8'))
    access_token=json_data['access_token']
    tokentime=float(json_data['expires_in'])-20+time.time()
    # 比过期时间提前20秒作废旧token
    return access_token

# 把从微信服务器获取的消息中的xml解析然后保存成dict
def  xml2dict(xmlbody):
    data_dict={}
    try:
        doc = etree.fromstring(xmlbody)  
    except Exception as e:
        print ('Error:connot parse xmlbody')
    # 从xml中提取需要的信息
    data_dict['ToUserName']=doc.find('ToUserName').text
    data_dict['FromUserName']=doc.find('FromUserName').text
    data_dict['CreateTime']=doc.find('CreateTime').text
    data_dict['MsgType']=doc.find('MsgType').text
    data_dict['MsgId']=doc.find('MsgId').text
    if data_dict['MsgType']=='text':
        data_dict['Content']=doc.find('Content').text
    elif data_dict['MsgType']=='image':
        data_dict['PicUrl']=doc.find('PicUrl').text
        data_dict['MediaId']=doc.find('MediaId').text
    elif data_dict['MsgType']=='voice':
        data_dict['Format']=doc.find('Format').text
        data_dict['MediaId']=doc.find('MediaId').text
    elif data_dict['MsgType']=='video':
        data_dict['ThumbMediaId']=doc.find('ThumbMediaId').text
        data_dict['MediaId']=doc.find('MediaId').text
    elif data_dict['MsgType']=='shortvideo':
        data_dict['ThumbMediaId']=doc.find('ThumbMediaId').text
        data_dict['MediaId']=doc.find('MediaId').text
    elif data_dict['MsgType']=='location':
        data_dict['Location_X']=doc.find('Location_X').text
        data_dict['Location_Y']=doc.find('Location_Y').text
        data_dict['Scale']=doc.find('Scale').text
        data_dict['Lable']=doc.find('Lable').text
    elif data_dict['MsgType']=='link':
        data_dict['Title']=doc.find('Title').text
        data_dict['Description']=doc.find('Description').text
        data_dict['Url']=doc.find('Url').text
    return data_dict
'''Tools end'''

'''各种不同情况的请求处理函数'''
# 用于响应微信服务器的请求
def wechat(environ,start_response):
    data=get_parameters(environ['QUERY_STRING'])
    body='success'
    # 用于微信公众号验证开发者服务器
    if environ['REQUEST_METHOD']=='GET'  and wechat_check(data) and 'echostr' in data :
        body = data['echostr']
    start_response('200 OK', [('Content-Type', 'text/html')])
    return [body.encode('utf-8')]
    # 暂时统一回复success。
    # 扩展为转发给其他程序处理？
    # 不同情况交给不同的逻辑去处理，有需要再扩展。

# 对外提供AccessToken,用于别的项目接口调试
def getaccesstoken(environ,start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [get_access_token().encode('utf-8')]

# 请求了未定义的路径
def notfound(environ, start_response):
    status = '404 NotFound'
    headers = [('Content-type', 'text/plain')]
    start_response(status, headers)
    return [status.encode('GBK')]

# 没有提供正确的调用码
def wrongcallcode(environ, start_response):
    status = '401 Unauthorized'
    headers = [('Content-type', 'text/plain')]
    start_response(status, headers)
    body = "请提供正确的callcode"
    #return body.encode('GBK')
    return [body.encode('GBK')]

# 用于接收消息请求,转发到微信
def index(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    body="消息发送失败,需提供接收者（touser）的OPENID和消息内容（content）"
    # 暂时只实现文本消息转发，有需求再继续扩展？
    data=get_parameters(environ['QUERY_STRING'])
    if('touser' in data and 'content' in data):
        # 处理转发到微信
        content=parse.unquote(data['content'])
        message={"msgtype": "text",
            'touser':data['touser'],
            'text':{'content':content}}
        # 中文编码问题，要统一编码utf-8，不然不同的地方调用还是会出现乱码
        messagejson=json.dumps(message,ensure_ascii = False) # ensure_ascii = False指定不转换为ascii码
        senddata=bytes(messagejson,'utf8') # post请求的data要用bytes
        req=request.Request(url=message_URL+'?access_token='+get_access_token(),data=senddata)
        res=request.urlopen(req)
        returnvalue=json.loads(res.read().decode('utf-8'))
        if('errmsg' in returnvalue and returnvalue['errmsg']=='ok'):
            body = "<div>消息发送成功！errmsg: %s errcode: %s </div>" % (returnvalue['errmsg'],returnvalue['errcode'])
        else:
            body = "<div>消息发送<b>No</b>成功！errmsg: %s errcode: %s </div>" % (returnvalue['errmsg'],returnvalue['errcode'])
            print (returnvalue)

    start_response(status, headers)
    #body = '<h1>Test, %s!</h1>' % (environ['PATH_INFO'][1:] )
    #return [bytes(body.encode('utf8'))]
    #return body.encode('gb2312')  #可行
    return [body.encode('GBK')]  #可行
    # 编码问题还是有点晕，再找点资料看？

# 请求处理函数,依据不同的PATH_INFO等参数，调用不同函数处理请求
def app(environ, start_response):
    # 响应微信服务器的验证，以及接受微信服务器发送过来的消息
    if(environ['PATH_INFO']=="/wechat"):
        return wechat(environ,start_response)
    # 判断是否提供了正确的callcode，如果callcode错误统一返回错误页面
    if(checkcallcode(environ['QUERY_STRING'])):
        return wrongcallcode(environ,start_response)
    # 别的应用获取access_token，转到相应处理函数
    if(environ['PATH_INFO']=="/getaccesstoken"):
        return getaccesstoken(environ,start_response)
    # 根路径用来接收要转发的文本消息
    if(environ['PATH_INFO']=="/"):
        return index(environ,start_response)
    # 都不符合的显示404错误
    return notfound(environ,start_response)

def test(environ,start_response):
    status = '200 OK'
    headers = [('Content-type', 'text/plain')]
    start_response(status, headers)
    ret = ["%s: %s\n" % (key, value)
        for key, value in environ.iteritems()]
    return ret

# 创建一个服务器，IP地址默认，端口是80，处理函数是app
# 微信公众号只允许使用80端口来接收微信服务器发送过来的消息
httpd = make_server('', 80, app)
print('Serving HTTP on port 80...')
# 开始监听HTTP请求:
httpd.serve_forever()
