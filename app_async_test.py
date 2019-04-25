import yaml
import docker
from sanic import Sanic
from sanic.response import json
from queue import Queue
from threading import Thread

app = Sanic()
NUM_WORKERS = 5
client = docker.from_env()

class TaskQueue(Queue):

    def __init__(self, num_workers=1):
        Queue.__init__(self)
        self.num_workers = num_workers
        self.start_workers()

    def add_task(self, task, *args, **kwargs):
        args = args or ()
        kwargs = kwargs or {}
        self.put((task, args, kwargs))

    def start_workers(self):
        for i in range(self.num_workers):
            t = Thread(target=self.worker)
            t.daemon = True
            t.start()

    def worker(self):
        while True:
            data = self.get()
            func, args, kwargs = self.get()
            image = func(*args, **kwargs)
            self.task_done()
            return image


def pull_image_and_build(client, image, name, command, ports):
    builded_image = client.images.pull(image)
    cont = client.containers.run(name=name, image=builded_image, command=command, ports=ports, detach=True)
    return json({'container id': cont.id})


@app.route('/start', methods=['POST'])
async def build_and_run_container(request):
    input_file = request.files.get('file')
    with open(input_file.name, 'r') as ymlfile:
        docker_config = yaml.safe_load(ymlfile)
    for key, value in docker_config.items():
        dicti = docker_config[key]
    name = list(docker_config.keys())[0]
    run_params = dicti.get('properties')
    image = run_params.get('image')+':latest'
    command = run_params.get('command')
    ports = run_params.get('port_bindings')[0]
    print(ports)
    try:
        builded_image = client.images.get(name=image)
    except:
        builded_image = client.images.pull(name=image)
    cont = client.containers.run(name=name, image=builded_image, command=command, ports=ports, detach=True)
    return json({'container id': cont.id})


@app.route('/stop/<cont_id>', methods=['POST'])
async def stop_container(request, cont_id):
    cont = client.containers.get(cont_id)
    cont.stop()
    cont.remove()
    return json({'status': 'stoped and removed'})


@app.route('/list', methods=['GET'])
def list_containers(request):
    containers = client.containers.list(all=True)
    output = {}
    for cont in containers:
        output[cont.name] = {'CONTAINER ID': cont.id,
                             'IMAGE': cont.attrs.get('Image'),
                             'COMMAND': cont.attrs.get('Config').get('Cmd'),
                             'CREATED': cont.attrs.get('Created'),
                             'STATUS': cont.attrs.get('State').get('Status'),
                             'PORTS': cont.attrs.get('HostConfig').get('PortBindings'),
                             }
    return json({'containers': output})


if __name__ == '__main__':
    q = TaskQueue(num_workers=5)
    app.run(host='0.0.0.0', port=8000, workers=2)
    #app.create_server(host='0.0.0.0', port=8000)
