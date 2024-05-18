---
- name: Initial setup and configuration
  hosts: all
  become: true
  strategy: free
  tasks:
    - name: Wait 300 seconds for port 22
      ansible.builtin.wait_for:
        port: 22 
        host: "{{ (ansible_ssh_host|default(ansible_host))|default(inventory_hostname) }}" 
        search_regex: OpenSSH 
        delay: 10 
        timeout: 300

    - name: Debug info
      ansible.builtin.shell:
        cmd: |
          echo DEBUG_1:{{ ansible_host }}
          echo DEBUG_2:${ansible_host}

    - name: Disable swap on each node
      ansible.builtin.shell: swapoff -a

    - name: Configure prerequisites
      ansible.builtin.shell:
        cmd: |
          cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
          overlay
          br_netfilter
          EOF

    - name: Load overlay module
      community.general.modprobe:
        name: overlay
        state: present

    - name: Load br_netfilter module
      community.general.modprobe:
        name: br_netfilter
        state: present

    - name: Sysctl params required by setup
      ansible.builtin.shell:
        cmd: |
          cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
          net.bridge.bridge-nf-call-iptables = 1
          net.bridge.bridge-nf-call-ip6tables = 1
          net.ipv4.ip_forward = 1
          EOF

    - name: Apply sysctl params without reboot
      ansible.builtin.shell: sysctl --system

    - name: Create containerd config file
      ansible.builtin.shell: mkdir -p /etc/containerd && touch /etc/containerd/config.toml

    - name: Install containerd prerequisites
      apt:
        name:
          - apt-transport-https
          - ca-certificates
          - lsb-release
          - curl
          - gnupg
        state: present

    - name: Create keyrings directory
      file: 
        path: /etc/apt/keyrings
        state: directory
        mode: '0755'

    - name: Add docker gpg key
      shell: |
        sudo rm -f /etc/apt/keyrings/docker.gpg
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg

    - name: Add docker repository
      shell: |
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    - name: Update apt and install docker-ce
      apt:
        name: 
          - docker-ce
          - docker-ce-cli
          - containerd.io 
        state: present
        update_cache: yes

    - name: Enable containerd
      ansible.builtin.systemd:
        name: containerd
        daemon_reload: yes
        state: started
        enabled: yes

    - name: Configure systemd cgroup driver for containerd
      ansible.builtin.copy:
        backup: true
        src: "{{ lookup('env', 'GITHUB_WORKSPACE') }}/config.toml"
        dest: /etc/containerd/config.toml

    - name: Restart containerd and daemon-reload to update config
      ansible.builtin.systemd:
        state: restarted
        daemon_reload: yes
        name: containerd

    - name: Download google cloud's public key
      ansible.builtin.apt_key:
        url: https://packages.cloud.google.com/apt/doc/apt-key.gpg
        state: present

    - name: Update apt package index
      apt:
        update_cache: true

    - name: Prepare install kube
      shell: |
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        sudo rm -f /etc/apt/keyrings/kubernetes-apt-keyring.gpg
        curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.30/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
        echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.30/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
        sudo apt-get update

    - name: Install kubeadm, kubectl, kubelet
      ansible.builtin.apt:
        pkg:
          - kubelet
          - kubeadm
          - kubectl

    - name: Hold kubectl,kubeadm,kubelet versions
      ansible.builtin.shell: apt-mark hold kubelet kubectl kubeadm

- name: Configure the master node
  hosts: master
  become: true
  tasks:
    - name: Init kubeadm
      ansible.builtin.shell: sudo kubeadm init --pod-network-cidr=10.244.0.0/16 --control-plane-endpoint "{{ ansible_host }}:6443"

    - name: Create ~/.kube directory
      ansible.builtin.file:
        path: ~/.kube
        state: directory

    - name: Copy kubeconfig file
      shell: sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config

    - name: Set permission on kubeconfig file
      shell: sudo chown $(id -u):$(id -g) $HOME/.kube/config

    - name: Install weavenet pod network add-on
      ansible.builtin.shell: kubectl apply -f https://github.com/weaveworks/weave/releases/download/v2.8.1/weave-daemonset-k8s.yaml

    - name: Generate token to join worker nodes to cluster
      ansible.builtin.shell: sudo kubeadm token create --print-join-command
      register: join_node_token
      delegate_to: localhost

- name: Join worker nodes to cluster
  hosts: workernode
  become: true
  tasks:
    - name: Save join token command as variable
      ansible.builtin.set_fact:
        join_node: "{{ hostvars['master'].join_node_token.stdout_lines[0] }}"

    - name: Add worker nodes to cluster
      shell: "sudo {{ join_node }}"
