"""Trình thực thi công cụ IoT trên thiết bị"""

import json
import asyncio
from typing import Dict, Any
from ..base import ToolType, ToolDefinition, ToolExecutor
from plugins_func.register import Action, ActionResponse


class DeviceIoTExecutor(ToolExecutor):
    """Trình thực thi công cụ IoT trên thiết bị"""

    def __init__(self, conn):
        self.conn = conn
        self.iot_tools: Dict[str, ToolDefinition] = {}

    async def execute(
        self, conn, tool_name: str, arguments: Dict[str, Any]
    ) -> ActionResponse:
        """执行设备端IoT工具"""
        if not self.has_tool(tool_name):
            return ActionResponse(
                action=Action.NOTFOUND, response=f"Công cụ IoT {tool_name} không tồn tại"
            )

        try:
            # 解析工具名称，获取设备名 và thao tác (cú pháp: get_devicename_property)
            if tool_name.startswith("get_"):
                parts = tool_name.split("_", 2)
                if len(parts) >= 3:
                    device_name = parts[1]
                    property_name = parts[2]

                    value = await self._get_iot_status(device_name, property_name)
                    if value is not None:
                        # 处理响应模板
                        response_success = arguments.get(
                            "response_success", "Truy vấn thành công: {value}"
                        )
                        response = response_success.replace("{value}", str(value))

                        return ActionResponse(
                            action=Action.RESPONSE,
                            response=response,
                        )
                    else:
                        response_failure = arguments.get(
                            "response_failure", f"Không thể lấy trạng thái của {device_name}"
                        )
                        return ActionResponse(
                            action=Action.ERROR, response=response_failure
                        )
            else:
                # 控制操作：devicename_method
                parts = tool_name.split("_", 1)
                if len(parts) >= 2:
                    device_name = parts[0]
                    method_name = parts[1]

                    # 提取控制参数（排除响应参数）
                    control_params = {
                        k: v
                        for k, v in arguments.items()
                        if k not in ["response_success", "response_failure"]
                    }

                    # 发送IoT控制命令
                    await self._send_iot_command(
                        device_name, method_name, control_params
                    )

                    # 等待状态更新
                    await asyncio.sleep(0.1)

                    # Lấy nội dung phản hồi thành công từ arguments
                    response_success = arguments.get("response_success", "Đã thực hiện lệnh thành công")

                    if response_success == "操作成功" or response_success == "Success" or response_success == "Đã thực hiện lệnh thành công":
                        # Chỉnh lại cho đúng phong cách Nanny Assistant
                        if "quat" in tool_name:
                            if "off" in method_name or "stop" in method_name or "tat" in method_name:
                                response_success = "Dạ, em đã tắt quạt rồi ạ!"
                            else:
                                response_success = "Dạ, em đã bật quạt cho bé rồi ạ!"
                        elif "cradle" in tool_name or "noi" in tool_name:
                            if "off" in method_name or "stop" in method_name:
                                response_success = "Dạ, em đã dừng nôi rồi ạ!"
                            else:
                                response_success = "Dạ, em đang bật nôi ru bé đây ạ!"

                    return ActionResponse(
                        action=Action.REQLLM,
                        result=response_success,
                    )

            return ActionResponse(action=Action.ERROR, response="Không thể phân tích tên công cụ IoT")

        except Exception as e:
            response_failure = arguments.get("response_failure", "Thao tác thất bại")
            return ActionResponse(action=Action.ERROR, response=response_failure)

    async def _get_iot_status(self, device_name: str, property_name: str):
        """获取IoT设备状态"""
        for key, value in self.conn.iot_descriptors.items():
            if key.lower() == device_name.lower():
                for property_item in value.properties:
                    if property_item["name"].lower() == property_name.lower():
                        return property_item["value"]
        return None

    async def _send_iot_command(
        self, device_name: str, method_name: str, parameters: Dict[str, Any]
    ):
        """发送IoT控制命令"""
        for key, value in self.conn.iot_descriptors.items():
            if key.lower() == device_name.lower():
                for method in value.methods:
                    if method["name"].lower() == method_name.lower():
                        command = {
                            "name": key,
                            "method": method["name"],
                        }

                        if parameters:
                            command["parameters"] = parameters

                        send_message = json.dumps(
                            {"type": "iot", "commands": [command]}
                        )
                        await self.conn.websocket.send(send_message)
                        return

        raise Exception(f"Không tìm thấy phương thức {method_name} cho thiết bị {device_name}")

    def register_iot_tools(self, descriptors: list):
        """注册IoT工具"""
        for descriptor in descriptors:
            device_name = descriptor["name"]
            device_desc = descriptor["description"]

            # 注册查询工具
            if "properties" in descriptor:
                for prop_name, prop_info in descriptor["properties"].items():
                    tool_name = f"get_{device_name.lower()}_{prop_name.lower()}"

                    tool_desc = {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": f"Truy vấn {prop_info['description']} của {device_desc}",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "response_success": {
                                        "type": "string",
                                        "description": f"Câu trả lời khi truy vấn thành công, phải sử dụng {{value}} để đại diện cho giá trị tìm được",
                                    },
                                    "response_failure": {
                                        "type": "string",
                                        "description": f"Câu trả lời khi truy vấn thất bại",
                                    },
                                },
                                "required": ["response_success", "response_failure"],
                            },
                        },
                    }

                    self.iot_tools[tool_name] = ToolDefinition(
                        name=tool_name,
                        description=tool_desc,
                        tool_type=ToolType.DEVICE_IOT,
                    )

            # 注册控制工具
            if "methods" in descriptor:
                for method_name, method_info in descriptor["methods"].items():
                    tool_name = f"{device_name.lower()}_{method_name.lower()}"

                    # 构建参数
                    parameters = {}
                    required_params = []

                    # 添加方法的原始参数
                    if "parameters" in method_info:
                        parameters.update(
                            {
                                param_name: {
                                    "type": param_info["type"],
                                    "description": param_info["description"],
                                }
                                for param_name, param_info in method_info[
                                    "parameters"
                                ].items()
                            }
                        )
                        required_params.extend(method_info["parameters"].keys())

                    # 添加响应参数
                    parameters.update(
                        {
                            "response_success": {
                                "type": "string",
                                "description": "Câu trả lời thân thiện khi thao tác thành công",
                            },
                            "response_failure": {
                                "type": "string",
                                "description": "Câu trả lời thân thiện khi thao tác thất bại",
                            },
                        }
                    )
                    required_params.extend(["response_success", "response_failure"])

                    tool_desc = {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": f"{device_desc} - {method_info['description']}",
                            "parameters": {
                                "type": "object",
                                "properties": parameters,
                                "required": required_params,
                            },
                        },
                    }

                    self.iot_tools[tool_name] = ToolDefinition(
                        name=tool_name,
                        description=tool_desc,
                        tool_type=ToolType.DEVICE_IOT,
                    )

    def get_tools(self) -> Dict[str, ToolDefinition]:
        """获取所有设备端IoT工具"""
        return self.iot_tools.copy()

    def has_tool(self, tool_name: str) -> bool:
        """检查是否有指定的设备端IoT工具"""
        return tool_name in self.iot_tools
