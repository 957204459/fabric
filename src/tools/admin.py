from django.contrib import admin
from .models import Settings, DeployLog, FrontEnd, DeployStart
import datetime
from fabric import Connection
from django.conf import settings
import os
import logging

log = logging.getLogger(__name__)


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    date_hierarchy = 'created'
    search_fields = ('name', 'status')
    list_display = ('id', 'created', 'name', 'git_branch', 'server_flag', 'server_ip', 'git_url', 'by_user', 'memo')
    list_display_links = ['id', 'created', 'name', 'git_branch', 'server_flag', 'server_ip', 'git_url', 'by_user', 'memo']
    exclude = ('by_user',)
    actions = ('check_info', 'deploy_project', )
    ordering = ['-id']
    change_list_template = "tools/change_list2.html"

    def check_info(self, request, queryset):
        qs = queryset[0]
        user_flag = qs.user_flag
        # pyer用户
        if user_flag == 1:
            ssh_user = 'pyer'
            # 测试环境
            if qs.server_flag == 1:
                ssh_pwd = settings.TST_PYER_PWD
                # 生产环境
            elif qs.server_flag == 2:
                ssh_pwd = settings.PRD_PYER_PWD
        # root 用户
        elif user_flag == 2:
            ssh_user = 'root'
            if qs.server_flag == 1:  # 测试环境
                ssh_pwd = settings.TST_ROOT_PWD
            elif qs.server_flag == 2:  # 生产环境
                ssh_pwd = settings.PRD_ROOT_PWD

        ssh_ip = qs.server_ip
        tmp_code_path = qs.tmp_code_path
        message_bit, ssh_flag, git_flag = '', False, False

        try:
            # 连接服务器
            con = Connection(ssh_user+'@'+ssh_ip, connect_kwargs={'password': ssh_pwd})
            git_url = qs.git_url
            # 检测git连接
            with con.cd(tmp_code_path):
                git_list = git_url.split('/')
                git_name = git_list[-1]
                if '.' in git_name:
                    git_name = git_name.split('.')[0]
                con.run('rm -rf ' + git_name)
                res = con.run('git clone ' + git_url)
                git_flag = True
                message_bit += '2.' + res.stdout
            ret = con.is_connected
            if ret:
                log.info('1.连接服务器成功....')
                ssh_flag = True
        except Exception as e:
            log.info('检查配置出错error:%s' % str(e))
        if ssh_flag and git_flag:
            message_bit = '服务器连接正常'
        else:
            message_bit = '服务器连接异常，请查看日志'
        self.message_user(request, '%s' % message_bit)

    check_info.short_description = '检查配置信息'

    def deploy_project(self, request, queryset):
        qs = queryset[0]
        user_flag = qs.user_flag
        server_flag = qs.server_flag
        ssh_ip = qs.server_ip
        code_path = qs.code_path
        before_cmd = qs.before_cmd
        before_list = before_cmd.split('\r\n') if before_cmd else []
        after_cmd = qs.after_cmd
        after_list = after_cmd.split('\r\n') if after_cmd else []
        git_url = qs.git_url
        git_branch = qs.git_branch
        git_list = git_url.split('/')
        git_name = git_list[-1]
        log_str, log_status = '', 0
        start_list = DeployStart.objects.filter(name=git_name, status=0)
        if not start_list:
            obj = DeployStart.objects.create(name=git_name, server_flag=server_flag, git_branch=git_branch,
                                             by_user=request.user, status=0)
            dobj = DeployLog.objects.create(by_user=request.user, project_flag=1,
                                            name=git_name, git_branch=git_branch, server_flag=server_flag)
            try:
                # pyer用户
                if user_flag == 1:
                    ssh_user = 'pyer'
                    # 测试环境
                    if qs.server_flag == 1:
                        ssh_pwd = settings.TST_PYER_PWD
                        # 生产环境
                    elif qs.server_flag == 2:
                        ssh_pwd = settings.PRD_PYER_PWD
                # root 用户
                elif user_flag == 2:
                    ssh_user = 'root'
                    if qs.flag == 1:  # 测试环境
                        ssh_pwd = settings.TST_ROOT_PWD
                    elif qs.flag == 2:  # 生产环境
                        ssh_pwd = settings.PRD_ROOT_PWD

                # 连接服务器
                con = Connection(ssh_user+'@'+ssh_ip, connect_kwargs={'password': ssh_pwd})
                log.info('1.连接%s@%s服务器完成:' % (ssh_user, ssh_ip))
                log_str += '1.连接%s@%s服务器完成:' % (ssh_user, ssh_ip)

                if '.' in git_name:
                    git_name = git_name.split('.')[0]
                log.info('2.获取git项目名称完成:%s' % git_url)
                log_str += '2.获取git项目名称完成:%s' % git_url
                # 检测git连接
                with con.cd(code_path + '/' + git_name):
                    log.info('3.进入目标路径完成:%s' % code_path + '/' + git_name)
                    log_str += '3.进入目标路径完成:%s' % code_path + '/' + git_name
                    for before_line in before_list:
                        if before_line:
                            con.run(before_line)
                            log.info('4.执行拉取前的操作完成:%s' % before_line)
                            log_str += '4.执行拉取前的操作完成:%s' % before_line
                    cmd = 'git pull origin ' + git_branch
                    log.info('5.执行拉取代码操作完成:%s' % cmd)
                    log_str += '5.执行拉取代码操作完成:%s' % cmd
                    con.run(cmd)
                    log.info('6.拉取代码完成;')
                    log_str += '6.拉取代码完成;'
                    for after_line in after_list:
                        if after_line:
                            con.run(after_line)
                            log.info('7.执行拉取后的操作完成:%s' % after_line)
                            log_str += '7.执行拉取后的操作完成:%s' % after_line
                    log.info('8.%s->发布成功...' % git_name)
                    log_str += '8.%s->发布成功...' % git_name
                    message_bit = '8.%s->发布成功...' % git_name
                    log_status = 1
            except Exception as e:
                log.error('发布出错error:%s', str(e))
                log_str += 'error:%s' % str(e)
                message_bit = '发布失败，详情请查看日志。'
            DeployStart.objects.filter(id=obj.id).update(status=1)
            DeployLog.objects.filter(id=dobj.id).update(content=log_str, status=log_status)

        else:
            message_bit='该%s项目有人正在发布，请等待...' % git_name
        self.message_user(request, '%s' % message_bit)

    deploy_project.short_description = '一键发布'

    def response_post_save_add(self, request, obj):
        user = request.user
        obj.by_user = user  # 添加人
        obj.save()
        return super(SettingsAdmin, self).response_post_save_add(request, obj)


@admin.register(FrontEnd)
class FrontEndAdmin(admin.ModelAdmin):
    date_hierarchy = 'created'
    search_fields = ('name', 'status')
    list_display = ('id', 'created', 'name', 'git_branch', 'server_flag', 'server_ip', 'git_url', 'by_user', 'memo')
    list_display_links = ['id', 'created', 'name', 'git_branch', 'server_flag', 'server_ip', 'git_url', 'by_user', 'memo']
    exclude = ('by_user', 'before_cmd')
    actions = ('check_info', 'deploy_project', )
    ordering = ['-id']
    change_list_template = "tools/change_list.html"

    def check_info(self, request, queryset):
        qs = queryset[0]
        user_flag = qs.user_flag
        # pyer用户
        if user_flag == 1:
            ssh_user = 'pyer'
            # 测试环境
            if qs.server_flag == 1:
                ssh_pwd = settings.TST_PYER_PWD
                # 生产环境
            elif qs.server_flag == 2:
                ssh_pwd = settings.PRD_PYER_PWD
        # root 用户
        elif user_flag == 2:
            ssh_user = 'root'
            if qs.server_flag == 1:  # 测试环境
                ssh_pwd = settings.TST_ROOT_PWD
            elif qs.server_flag == 2:  # 生产环境
                ssh_pwd = settings.PRD_ROOT_PWD

        ssh_ip = qs.server_ip
        tmp_code_path = qs.tmp_code_path
        git_url = qs.git_url
        git_list = git_url.split('/')
        git_name = git_list[-1]
        if '.' in git_name:
            git_name = git_name.split('.')[0]
        message_bit, ssh_flag, git_flag = '', False, False

        try:
            log.info('检测项目状态...')

            # 连接服务器
            con = Connection(ssh_user+'@'+ssh_ip, connect_kwargs={'password': ssh_pwd})
            with con.cd('~'):
                con.run('ls')
            ret = con.is_connected
            if ret:
                log.info('1.连接服务器完成....')
                ssh_flag = True
            os.system('rm -rf ' + tmp_code_path + '/' + git_name)
            log.info('rm -rf ' + tmp_code_path + '/' + git_name)
            os.system('git clone ' + git_url + ' ' + tmp_code_path + '/' + git_name)
            log.info('git clone ' + git_url + ' ' + tmp_code_path + '/' + git_name)
            log.info('2.拉取代码完成....')
            git_flag = True
        except Exception as e:
            log.info('检查配置出错error:%s', str(e))
        if ssh_flag and git_flag:
            message_bit = '服务器连接正常'
        else:
            message_bit = '服务器连接异常，请查看日志'
        self.message_user(request, '%s' % message_bit)

    check_info.short_description = '检查配置信息'

    def deploy_project(self, request, queryset):
        qs = queryset[0]
        user_flag = qs.user_flag
        server_flag = qs.server_flag
        ssh_ip = qs.server_ip
        code_path = qs.code_path
        tmp_code_path = qs.tmp_code_path
        before_cmd = qs.before_cmd
        before_list = before_cmd.split('\r\n') if before_cmd else []
        after_cmd = qs.after_cmd
        after_list = after_cmd.split('\r\n') if after_cmd else []
        git_branch = qs.git_branch
        git_url = qs.git_url
        git_list = git_url.split('/')
        git_name = git_list[-1]
        log_str, log_status = '', 0
        start_list = DeployStart.objects.filter(name=git_name, status=0)
        if not start_list:
            obj = DeployStart.objects.create(name=git_name, server_flag=server_flag, git_branch=git_branch,
                                             by_user=request.user, status=0)
            dobj = DeployLog.objects.create(by_user=request.user, project_flag=1,
                                            name=git_name, git_branch=git_branch, server_flag=server_flag)
            # pyer用户
            if user_flag == 1:
                ssh_user = 'pyer'
                # 测试环境
                if qs.server_flag == 1:
                    ssh_pwd = settings.TST_PYER_PWD
                    # 生产环境
                elif qs.server_flag == 2:
                    ssh_pwd = settings.PRD_PYER_PWD
            # root 用户
            elif user_flag == 2:
                ssh_user = 'root'
                if qs.flag == 1:  # 测试环境
                    ssh_pwd = settings.TST_ROOT_PWD
                elif qs.flag == 2:  # 生产环境
                    ssh_pwd = settings.PRD_ROOT_PWD

            if '.' in git_name:
                git_name = git_name.split('.')[0]
            try:
                # 本地代码拉取--打包
                os.chdir(tmp_code_path)
                log.info('0.进入打包目录:' + tmp_code_path)
                log_str += '0.进入打包目录:' + tmp_code_path
                if os.path.exists(git_name):
                    cmd = '0.' + tmp_code_path + '下面存在' + git_name + '目录'
                    log.info(cmd)
                    log_str += cmd
                    try:
                        cmd = tmp_code_path + '/' + git_name
                        os.chdir(cmd)
                        log.info('0.进入项目' + cmd)
                        log_str += '0.进入项目' + cmd
                        cmd = 'git branch -a'
                        os.system(cmd)
                        log.info('1.连接远端分支' + cmd)
                        log_str += '1.连接远端分支' + cmd
                        cmd = ' git checkout ' + git_branch
                        log.info('1.切换分支' + cmd)
                        log_str += '1.切换分支' + cmd
                        os.system(cmd)
                        cmd = ' git pull origin ' + git_branch
                        log.info('1.获取最新代码' + cmd)
                        log_str += '1.获取最新代码' + cmd
                        os.system(cmd)
                    except Exception as e:
                        log.error('0.项目error' + str(e))
                        cmd = 'rm -rf ' + git_name
                        os.system(cmd)
                        log.info('1.删除已存在的项目:' + cmd)
                        log_str += '1.删除已存在的项目:' + cmd
                else:
                    cmd = 'git clone ' + '-b ' + git_branch + ' ' + git_url
                    os.system(cmd)
                    log.info('2.克隆指定分支代码:' + cmd)
                    log_str += '2.克隆指定分支代码:' + cmd
                    # 打包操作
                    cmd = tmp_code_path + '/' + git_name
                    log.info('3.进入' + cmd)
                    os.chdir(cmd)
                log.info('3.执行yarn命令:yarn')
                log_str += '3.执行yarn命令:yarn'
                yarn_line = os.popen('yarn')  # 执行该命令
                info = yarn_line.readlines()  # 读取命令行的输出到一个list
                for line in info:  # 按行遍历
                    line = line.strip('\r\n')
                    log.info('[yarn]' + line)

                log.info('3.执行npm命令:npm run build')
                log_str += '3.执行npm命令:npm run build'
                npm_line = os.popen('npm run build')
                info = npm_line.readlines()  # 读取命令行的输出到一个list
                for line in info:  # 按行遍历
                    line = line.strip('\r\n')
                    log.info('[npm]' + line)
                cmd = tmp_code_path + '/' + git_name + ''
                os.chdir(cmd)
                os.system('rm -rf dist.zip')
                log.info('4.进入打包路径:' + cmd)
                log_str += '4.进入打包路径:' + cmd
                cmd = 'zip -r dist.zip dist'
                os.system(cmd)
                log.info('4.开始打包文件:' + cmd)
                log_str += '4.开始打包文件:' + cmd
                # 连接服务器
                con = Connection(ssh_user+'@'+ssh_ip, connect_kwargs={'password': ssh_pwd})
                log.info('5.连接服务器%s@%s完成' % (ssh_user, ssh_ip))
                log_str += '5.连接服务器%s@%s完成' % (ssh_user, ssh_ip)
                with con.cd(code_path):
                    con.run('rm -rf dist.zip')
                    cmd = (tmp_code_path + '/' + git_name + '.zip', code_path + '/' + git_name + '.zip')
                    con.put(tmp_code_path + '/' + git_name + '/dist.zip', code_path + '/dist.zip')
                    log.info('6.上传zip文件:' + str(cmd))
                    log_str += '6.上传zip文件:' + str(cmd)
                    cmd = 'rm -rf dist2/'
                    con.run(cmd)
                    log.info('7.删除以前备份文件:' + cmd)
                    log_str += '7.删除以前备份文件:' + cmd
                    cmd = 'mv dist dist2'
                    con.run(cmd)
                    log.info('7.开始备份文件:' + cmd)
                    log_str += '7.开始备份文件:' + cmd
                    cmd = 'unzip dist.zip'
                    con.run(cmd)
                    log.info('9.解压文件:' + cmd)
                    log_str += '9.解压文件:' + cmd
                    message_bit = '发布成功...'
                    log_status = 1
                log.info('10.%s->发布成功...' % git_name)
                log_str += '10.%s->发布成...' % git_name
            except Exception as e:
                log.error('发布出错error:%s' % str(e))
                log_str += 'error:%s' % str(e)
                message_bit = '发布失败，详情请查看日志。'
            DeployStart.objects.filter(id=obj.id).update(status=1)
            DeployLog.objects.filter(id=dobj.id).update(content=log_str, status=log_status)

        else:
            message_bit = '该%s项目有人正在发布，请等待...' % git_name
        self.message_user(request, '%s' % message_bit)

    deploy_project.short_description = '一键发布'

    def response_post_save_add(self, request, obj):
        user = request.user
        obj.by_user = user  # 添加人
        obj.save()
        return super(FrontEndAdmin, self).response_post_save_add(request, obj)


@admin.register(DeployStart)
class DeployStartAdmin(admin.ModelAdmin):
    date_hierarchy = 'created'
    search_fields = ('name', 'status')
    list_display = ('id', 'created', 'name', 'git_branch', 'server_flag', 'status', 'by_user')
    list_display_links = ['id', 'created', 'name', 'git_branch', 'server_flag', 'status', 'by_user']
    ordering = ['-id']
    readonly_fields = ('name', 'git_branch', 'server_flag', 'status', 'by_user')


@admin.register(DeployLog)
class DeployLogAdmin(admin.ModelAdmin):
    date_hierarchy = 'created'
    search_fields = ('by_user', 'status')
    list_display = ('id', 'created', 'name', 'git_branch', 'server_flag', 'project_flag', 'content', 'by_user', 'status')
    list_display_links = ['id', 'created', 'name', 'git_branch', 'server_flag', 'project_flag', 'content', 'by_user', 'status']
    ordering = ['-id']
    readonly_fields = ('name', 'git_branch', 'server_flag',  'project_flag', 'by_user', 'content', 'status')


admin.site.disable_action('delete_selected')