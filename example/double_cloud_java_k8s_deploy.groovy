def call(body) {

    def config = [:]
    body.resolveStrategy = Closure.DELEGATE_FIRST
    body.delegate = config
    body()
    def generateParams = new com.volvo.Params()
    def utils = new com.volvo.Utils()
    def gitlab = new com.volvo.GitLab()
    def mvn = new com.volvo.Maven()
    def buildImg = new com.volvo.Build()
    def sonar = new com.volvo.SonarQube()
    def email = new com.volvo.Email()
    def k8s = new com.volvo.K8S()
    def log = new com.volvo.Log()
    def nacos = new com.volvo.Nacos()
    def opsapi = new com.volvo.OpsApi()

    appName_list = appName_list.AppName_list(config)

    generateParams.generateDoubleCloudJavaParamsProperties(config, appName_list)
    def imageTag = "${params.GitBranch}".trim() + "-" + new Date().format("yyyyMMddhhmmss") + "-" + "${params.DeployEnv}"
    def kanikoApp = "kaniko-${params.AppName.trim()}"
    def huaweiyun_deploy_kubeconfig_path = ""
    def aliyun_deploy_kubeconfig_path = "/root/.kubedeploy/${params.DeployEnv}_aliyun_config"
    def deployNumber = 0
    def resultJson = ["test_fail": "", "test_count": "", "test_pass": "", "branch_coverage": "", "line_coverage": "", "instruction_coverage": "", "class_coverage": "", "method_coverage": "", "complexity_coverage": ""]
    def resultJson_inc = ["inc_branch_coverage": "", "inc_line_coverage": "", "inc_instruction_coverage": "", "inc_complexity_coverage": "", "inc_method_coverage": "", "inc_class_coverage": ""]
    def swagger_scanner_result = ["scan_result": ""]
    def COMMIT_ID = ""

    pipeline {
        agent {
            kubernetes {
                yaml podTemplateNewbieJava(params.DeployEnv)
            }
        }

        options {
            timestamps()                // Console开启时间显示
            ansiColor('xterm')          // 控制台输出增加颜色支持
        }

        environment {
            GIT_CREDENTIAL_ID = "${config.git_credential_id}"
            NEWBIE_GIT_CREDENTIAL_ID = "${config.newbie_git_credential_id}"
            apm_access_key = credentials("${params.DeployEnv}_apm_access_key")
            apm_access_value = credentials("${params.DeployEnv}_apm_access_value")
            icd_apm_access_key = credentials("icd_${params.DeployEnv}_apm_access_key")
            icd_apm_access_value = credentials("icd_${params.DeployEnv}_apm_access_value")
            rfp_apm_access_key = credentials("rfp_${params.DeployEnv}_apm_access_key")
            rfp_apm_access_value = credentials("rfp_${params.DeployEnv}_apm_access_value")
        }

        stages {

            stage("Preparation") {
                steps {
                    script {
                        if (params.DeployMethod == "Image") {
                            imageTag = params.ImageTag.trim()
                        }
                        //ops平台回调
                        if ("${params.BuildHistoryId}" != null && "${params.BuildHistoryId}" != "") {
                            opsapi.callBack(imageTag, "", resultJson, resultJson_inc, COMMIT_ID)
                        }
                        env.stage = ""
                        print("${BUILD_NUMBER}")
                        utils.printStageBegin("Preparation")

                        print(imageTag)
                        currentBuild.description =
                                "Env: " + params.DeployEnv + "\n" +
                                        "AppName: " + params.AppName + "\n" +
                                        "Branch: " + params.GitBranch + "\n" +
                                        "ImageTag: " + imageTag + "\n" +
                                        "SonarCheck: " + params.SonarEnable + "\n" +
                                        "Deploy: " + params.IsDeploy + "\n"
                        commonParams = utils.generateJavaCommonParams(params)
                        huaweiyun_deploy_kubeconfig_path = utils.check_huawei_kubeconfig_path(params.DeployEnv, commonParams.kubernetesClusterName, commonParams.DeployNamespace, config)
                        print(commonParams)
                        kanikoApp = "kaniko-${commonParams.AppName.trim()}"

                        //if (commonParams.Jdk_version == "azul") {
                        env.JAVA_HOME = "/usr/local/zulu8.33.0.1-jdk8.0.192-linux_x64"
                        // } else {
                        //     env.JAVA_HOME = "/usr/local/jdk1.8.0_391"
                        // }
                        env.PATH = "${env.JAVA_HOME}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/node-v16.20.2-linux-x64/bin:/usr/local/docker:/usr/local/kubernetes/client/bin:/usr/local/apache-maven-3.9.4/bin"

                        utils.printStageEnd("Preparation")
                    }
                }
            }

            stage("Checkout Code") {
                when {
                    equals expected: "SourceCode",
                            actual: params.DeployMethod
                }
                steps {
                    container('kubernetes') {
                        script {

                            // build wait: false, job: 'devsecops/DevSecOps-Scan-Java', 
                            //     parameters: [string(name: 'AppName', value: "${params.AppName}"), 
                            //                  string(name: 'SourceCodeGit', value: "${commonParams.GitUrl}"), 
                            //                  string(name: 'BranchName', value: "${params.GitBranch}")]

                            utils.printStageBegin("Checkout Code")
                            if (commonParams.AppName == "mweb-v216") {
                                gitlab.checkoutSource(commonParams.GitUrl, params.GitBranch, env.NEWBIE_GIT_CREDENTIAL_ID)
                            } else {
                                gitlab.checkoutSource(commonParams.GitUrl, params.GitBranch, env.GIT_CREDENTIAL_ID)
                            }
                            try {
                                sh "git config --global --add safe.directory '*'"
                                COMMIT_ID = sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
                            } catch (Exception e) {
                                println "${e}"
                            }

                            utils.printStageEnd("Checkout Code")
                        }
                    }
                }
            }

            stage("Maven Deploy") {
                when {
                    equals expected: "SourceCode",
                            actual: params.DeployMethod
                }
                steps {
                    container('kubernetes') {
                        script {
                            utils.printStageBegin("Maven Deploy")
                            if (params.AppName == 'ced-campaign' || params.AppName == 'ced-ci' || params.AppName == 'ced-cold-leads' || params.AppName == 'ced-data-dict' || params.AppName == 'ced-gateway' || params.AppName == 'ced-label' || params.AppName == 'ced-leads' || params.AppName == 'ced-portal-app' || params.AppName == 'xxl-job-admin' || params.AppName == 'ced-portal-message' || params.AppName == 'ced-portal-sso' || params.AppName == 'ced-security' || params.AppName == 'leads-receive' || params.AppName == 'ced-task' || params.AppName == 'ced-user-authorization' || params.AppName == 'leads-bi' || params.AppName == 'leads-clean' || params.AppName == 'leads-send' || params.AppName == 'leads-web-management') {
                                mvn.mavenCompile(commonParams.BuildDir, params.AppName.trim(), "")
                            } else {
                                mvn.mavenCompile(commonParams.BuildDir, commonParams.AppName, commonParams.mvnModule)
                            }
                            utils.printStageEnd("Maven Deploy")
                        }
                    }
                }
            }

            stage("Maven Unit Swagger") {
                parallel {
                    stage("Unit Test") {
                        when {
                            allOf {
                                equals expected: 'true', actual: params.UnitTest
                                //equals expected: 'true', actual: commonParams.UnitTest
                                equals expected: 'SourceCode', actual: params.DeployMethod
                            }
                        }
                        steps {
                            script {
                                container('kubernetes') {
                                    def UnitTestByJacoco = libraryResource "tool/UnitTestByJacoco.py"
                                    writeFile file: 'UnitTestByJacoco.py', text: UnitTestByJacoco

                                    def buildDir = "${commonParams.BuildDir}"

                                    if ("${commonParams.BuildDir}" == "" || "${commonParams.BuildDir}" == null) {
                                        buildDir = "./"
                                    }

                                    def scriptResult = sh(script: "python3 UnitTestByJacoco.py --build-dir ${buildDir} --failure-ignore ${params.FailureIgnore} --report-path ${commonParams.SonarSrcPath} --workspace ${WORKSPACE} --test-type full", returnStdout: true).trim()

                                    // 使用自定义分隔符分割输出
                                    def parts = scriptResult.split("##### json outputs here...", 2)

                                    if (parts.size() == 2) {
                                        // 解析JSON结果
                                        resultJson = readJSON text: parts[1]

                                        echo "Test Count: ${resultJson.test_count}"
                                        echo "Test Pass: ${resultJson.test_pass}"
                                        echo "Test Fail: ${resultJson.test_fail}"
                                        echo "Branch Coverage: ${resultJson.branch_coverage}"
                                        echo "Line Coverage: ${resultJson.line_coverage}"
                                        echo "Instruction_Coverage: ${resultJson.instruction_coverage}"
                                        echo "Class_Coverage: ${resultJson.class_coverage}"
                                        echo "Method_Coverage: ${resultJson.method_coverage}"
                                        echo "Complexity_Coverage: ${resultJson.complexity_coverage}"

                                        currentBuild.description +=
                                                "test_count:" + "${resultJson.test_count}" + "\n" +
                                                        "test_pass:" + "${resultJson.test_pass}" + "\n" +
                                                        "test_fail:" + "${resultJson.test_fail}" + "\n" +
                                                        "branch_coverage:" + "${resultJson.branch_coverage}" + "\n" +
                                                        "line_coverage:" + "${resultJson.line_coverage}" + "\n" +
                                                        "instruction_coverage:" + "${resultJson.instruction_coverage}" + "\n" +
                                                        "class_coverage:" + "${resultJson.class_coverage}" + "\n" +
                                                        "method_coverage:" + "${resultJson.method_coverage}" + "\n" +
                                                        "complexity_coverage:" + "${resultJson.complexity_coverage}" + "\n"
                                    }
                                }
                            }
                        }
                    }

                    stage("Check Status") {
                        when {
                            equals expected: "SourceCode",
                                    actual: params.DeployMethod
                        }
                        steps {
                            container('kubernetes') {
                                script {
                                    utils.printStageBegin("Check Status")
                                    result = buildImg.getKanikoAppName(config.kaniko_kubeconfig_path, kanikoApp, params.KanikoNamespace)
                                    if ("${result}" == "${kanikoApp}") {
                                        buildImg.deleteKanikoApp(config.kaniko_kubeconfig_path, kanikoApp, params.KanikoNamespace)
                                    }
                                    utils.printStageEnd("Check Status")
                                }
                            }
                        }
                    }

                    stage("Sonar Scan: Swagger") {
                        when {
                            allOf {
                                equals expected: "SourceCode", actual: params.DeployMethod
                                equals expected: 'true', actual: commonParams.SonarEnable
                            }
                        }
                        steps {
                            container('kubernetes') {
                                script {
                                    utils.printStageBegin("Sonar Scan: Swagger")
                                    def restApi_Scanner = libraryResource "tool/restApi_Scanner.py"
                                    writeFile file: 'restApi_Scanner.py', text: restApi_Scanner
                                    def buildDir = "${commonParams.BuildDir}"
                                    if ("${commonParams.BuildDir}" == "" || "${commonParams.BuildDir}" == null) {
                                        buildDir = "./"
                                    }
                                    def scriptResult = sh(script: "python restApi_Scanner.py --build-dir ${buildDir} " +
                                            "--workspace ${WORKSPACE}", returnStdout: true).trim()
                                    // 解析JSON结果
                                    def swaggerResultJson = readJSON text: scriptResult
                                    swagger_scanner_result.put("scan_result", swaggerResultJson.result)
                                    def swaggerACSEnable = params.SwaggerACSEnable;
                                    if (params.SwaggerACSEnable.toBoolean() && !swaggerResultJson.result.toBoolean()) {
                                        error "Swagger API 注解 扫描不通过，停止构建"
                                    }
                                    currentBuild.description +=
                                            "swagger_scanner_result:" + "${swaggerResultJson.result}" + "\n"
                                    echo "Performing additional step during Sonar Scan: Swagger."
                                    utils.printStageEnd("Sonar Scan: Swagger")
                                }
                            }
                        }
                    }

                }
            }

            stage("Sonar IncUnit Template") {
                parallel {
                    stage("Sonar Scan: Base") {
                        when {
                            allOf {
                                equals expected: "SourceCode", actual: params.DeployMethod
                                //equals expected: 'true', actual: params.SonarEnable
                                equals expected: 'true', actual: commonParams.SonarEnable
                            }
                        }
                        steps {
                            container('kubernetes') {
                                script {
                                    utils.printStageBegin("Sonar Scan: Base")
                                    sh "cp -rf ./server/target . || true"
                                    if (commonParams.SonarSrcPath != "./src" && commonParams.SonarSrcPath != "/src" && commonParams.SonarSrcPath != "") {
                                        target_dir = commonParams.SonarSrcPath.split("/src")[0] + "/target"
                                        sh "cp -rf ${target_dir} . || true"
                                    }
                                    //sonar.javaQAWithSwagger(commonParams.AppName,params.DeployEnv, config, commonParams.SonarSrcPath, commonParams)
                                    sonar.javaQA(commonParams.AppName, params.DeployEnv, config, commonParams.SonarSrcPath)
                                    utils.printStageEnd("Sonar Scan: Base")
                                }
                            }
                        }
                    }

                    stage("Inc Unit Test") {
                        when {
                            allOf {
                                equals expected: 'true', actual: params.IncUnitTest
                                equals expected: 'SourceCode', actual: params.DeployMethod
                            }
                        }
                        steps {
                            script {
                                container('kubernetes') {
                                    def UnitTestByJacoco = libraryResource "tool/UnitTestByJacoco.py"
                                    writeFile file: 'UnitTestByJacoco.py', text: UnitTestByJacoco

                                    def buildDir = "${commonParams.BuildDir}"

                                    if ("${commonParams.BuildDir}" == "" || "${commonParams.BuildDir}" == null) {
                                        buildDir = "./"
                                    }

                                    def scriptResult = sh(script: "python3 UnitTestByJacoco.py --build-dir ${buildDir} --failure-ignore ${params.FailureIgnore} --report-path ${commonParams.SonarSrcPath} --workspace ${WORKSPACE} --code-git-url ${commonParams.GitUrl} --base-branch ${params.BaseBranch} --now-branch ${params.GitBranch} --test-type inc", returnStdout: true).trim()

                                    // 使用自定义分隔符分割输出
                                    def parts = scriptResult.split("##### json outputs here...", 2)

                                    if (parts.size() == 2) {
                                        // 解析JSON结果
                                        resultJson_inc = readJSON text: parts[1]
                                        echo "Inc Branch Coverage: ${resultJson_inc.inc_branch_coverage}"
                                        echo "Inc Line Coverage: ${resultJson_inc.inc_line_coverage}"
                                        echo "Inc Instruction Coverage:  ${resultJson_inc.inc_instruction_coverage}"
                                        echo "Inc Complexity Coverage:  ${resultJson_inc.inc_complexity_coverage}"
                                        echo "Inc Method Coverage:  ${resultJson_inc.inc_method_coverage}"
                                        echo "Inc Class Coverage:  ${resultJson_inc.inc_class_coverage}"

                                        currentBuild.description +=
                                                "inc_branch_coverage:" + "${resultJson_inc.inc_branch_coverage}" + "\n" +
                                                        "inc_line_coverage:" + "${resultJson_inc.inc_line_coverage}" + "\n" +
                                                        "inc_instruction_coverage:" + "${resultJson_inc.inc_instruction_coverage}" + "\n" +
                                                        "inc_class_coverage:" + "${resultJson_inc.inc_class_coverage}" + "\n" +
                                                        "inc_method_coverage:" + "${resultJson_inc.inc_method_coverage}" + "\n" +
                                                        "inc_complexity_coverage:" + "${resultJson_inc.inc_complexity_coverage}"
                                    }
                                }
                            }
                        }
                    }

                    stage("Pull Build Template") {
                        steps {
                            script {
                                container('kubernetes') {
                                    utils.printStageBegin("Pull Build Template")
                                    copy_dir = [target_dir: "", startup_sh_file: ""]
                                    if (params.DeployMethod == "SourceCode") {
                                        copy_dir = buildImg.getTargetDirectoryPath(commonParams.BuildDir, commonParams.mvnModule, commonParams.DeployAppName)
                                    }
                                    log.info("target目录：${copy_dir}")
                                    dir("${commonParams.ServiceName}") {
                                        buildImg.pullBuildTemplate(commonParams.DeploymentGitUrl, env, params.DeployEnv, commonParams.DeployAppName, commonParams.mvnModule, copy_dir)
                                    }
                                    utils.printStageEnd("Pull Build Template")
                                }
                            }
                        }
                    }
                }
            }

            stage("Image Report") {
                parallel {

                    stage("Image Build") {
                        when {
                            equals expected: "SourceCode",
                                    actual: params.DeployMethod
                        }
                        steps {
                            container('kubernetes') {
                                script {
                                    utils.printStageBegin("Image Build")
                                    buildImg.kanikoBuild(config.kaniko_kubeconfig_path, imageTag, params.DeployEnv, kanikoApp, params.KanikoNamespace, commonParams.ServiceName, commonParams.AppName)
                                    utils.printStageEnd("Image Build")
                                }
                            }
                        }
                    }

                    stage('Report Test') {
                        when {
                            allOf {
                                equals expected: 'true', actual: params.IncUnitTest
                                equals expected: 'SourceCode', actual: params.DeployMethod
                            }
                        }
                        steps {
                            script {
                                container('kubernetes') {
                                    withCredentials([string(credentialsId: "devops_obs_prod_id", variable: 'devops_obs_prod_id'),
                                                    string(credentialsId: "devops_obs_prod_value", variable: 'devops_obs_prod_value'),
                                                    string(credentialsId: "devops_obs_endpoint", variable: 'devops_obs_endpoint'),
                                    ]) { // Shell脚本
                                        env.Tag = "${imageTag}"
                                        sh '''
                                    #!/bin/bash
                                    # 定义变量
                                    UNIT_REPORT="${AppName}:${Tag}"

                                    # 检查并下载 obsutil
                                    if [ ! -d "/tmp/obsutil_linux_amd64_5.5.12" ]; then
                                        wget -q https://obs-community.obs.cn-north-1.myhuaweicloud.com/obsutil/current/obsutil_linux_amd64.tar.gz && \
                                        tar -xzvf obsutil_linux_amd64.tar.gz -C /tmp && \
                                        chmod 755 "/tmp/obsutil_linux_amd64_5.5.12/obsutil"
                                    fi

                                    # 配置 obsutil
                                    cd /tmp/obsutil_linux_amd64_5.5.12 || exit
                                    ./obsutil config -i=${devops_obs_prod_id} -k=${devops_obs_prod_value} -e=${devops_obs_endpoint}

                                    # 检查 IncUnitTestReports 是否存在
                                    if [ -d "$WORKSPACE/IncUnitTestReports" ]; then
                                        mv "$WORKSPACE/IncUnitTestReports" "$WORKSPACE/$Tag"

                                        # 上传到 OBS
                                        ./obsutil mkdir obs://volvo-vdevops-prod/ops_incunit_report/${AppName}
                                        ./obsutil cp "$WORKSPACE/$Tag" "obs://volvo-vdevops-prod/ops_incunit_report/${AppName}/" -f -r
                                    else
                                        echo "错误: $WORKSPACE/IncUnitTestReports 不存在."
                                    fi
                                    '''
                                    }
                                }

                            }
                        }
                    }

                }
            }

            stage("Deploy") {
                when {
                    equals expected: 'true',
                            actual: params.IsDeploy
                }

                steps {
                    container('kubernetes') {
                        script {
                            utils.printStageBegin("HuaWei Cloud Deploy")
                            k8s.huaweiDeploy(env, huaweiyun_deploy_kubeconfig_path, imageTag, params.DeployEnv, deployNumber, commonParams.DeployAppName, commonParams.DeployNamespace, commonParams.ServiceName, params.RolloutStatusEnable, commonParams)
                            utils.printStageEnd("HuaWei Cloud Deploy")
                        }
                    }
                }
            }

        }

        post {
            always {
                // script {
                //     utils.jenkinsApplyConfig()
                // }
                echo 'Finished'

            }
            success {
                script {
                    email.sendEmail(commonParams.Email_receiver, "Succeed", false)
                    if ("${params.BuildHistoryId}" != null && "${params.BuildHistoryId}" != "") {
                        opsapi.callBack(imageTag, "Succeed", resultJson, resultJson_inc, COMMIT_ID)
                    }
                }
                echo 'I succeeeded!'
            }
            unstable {
                echo 'I am unstable :/'
            }
            failure {
                script {
                    email.sendEmail(commonParams.Email_receiver, "Failed", true)
                    if ("${params.BuildHistoryId}" != null && "${params.BuildHistoryId}" != "") {
                        opsapi.callBack(imageTag, "Failed", resultJson, resultJson_inc, COMMIT_ID)
                    }
                }
            }
            aborted {
                script {
                    email.sendEmail(commonParams.Email_receiver, "Failed", true)
                    if ("${params.BuildHistoryId}" != null && "${params.BuildHistoryId}" != "") {
                        opsapi.callBack(imageTag, "Failed", resultJson, resultJson_inc, COMMIT_ID)
                    }
                }
            }
        }
    }
}
